"""Utilities for working with datasets."""

import gc
import itertools
import json
import math
import os
import pprint
import secrets
from collections.abc import Iterable
from functools import partial
from typing import Any, Callable, Generator, Iterator, Optional, TypeVar, Union, cast

import numpy as np
import pyarrow as pa

from ..batch_utils import flatten_iter
from ..embeddings.vector_store import VectorDBIndex
from ..env import env
from ..parquet_writer import ParquetWriter
from ..schema import (
  EMBEDDING_KEY,
  PATH_WILDCARD,
  ROWID,
  SPAN_KEY,
  STRING,
  TEXT_SPAN_END_FEATURE,
  TEXT_SPAN_START_FEATURE,
  EmbeddingInfo,
  Field,
  Item,
  MapFn,
  PathKey,
  PathTuple,
  Schema,
  VectorKey,
  field,
  schema,
  schema_to_arrow_schema,
)
from ..signal import Signal
from ..utils import chunks, is_primitive, log, open_file

# The embedding write chunk sizes keeps the memory pressure lower as we iteratively write to the
# vector store. Embeddings are float32, taking up 4 bytes, so this results in ~1.25MB * dims of RAM
# pressure.
EMBEDDINGS_WRITE_CHUNK_SIZE = 327_680


def _replace_embeddings_with_none(input: Union[Item, Item]) -> Union[Item, Item]:
  if isinstance(input, np.ndarray):
    return None
  if isinstance(input, dict):
    return {k: _replace_embeddings_with_none(v) for k, v in input.items()}
  if isinstance(input, list):
    return [_replace_embeddings_with_none(v) for v in input]

  return input


def replace_embeddings_with_none(input: Union[Item, Item]) -> Item:
  """Replaces all embeddings with None."""
  return cast(Item, _replace_embeddings_with_none(input))


def count_leafs(input: Union[Iterable, Iterator]) -> int:
  """Iterate through each element of the input, flattening each one, computing a count.

  Sum the final set of counts. This is the important iterable not to exhaust.
  """
  return len(list(flatten_iter(input)))


def _wrap_value_in_dict(input: Union[object, dict], props: PathTuple) -> Union[object, dict]:
  # If the signal produced no value, or nan, we should return None so the parquet value is sparse.
  if isinstance(input, float) and math.isnan(input):
    input = None
  for prop in reversed(props):
    input = {prop: input}
  return input


def _wrap_in_dicts(
  input: Union[object, Iterable[object]], spec: list[PathTuple]
) -> Union[object, Iterable[object]]:
  """Wraps an object or iterable in a dict according to the spec."""
  props = spec[0] if spec else tuple()
  if len(spec) == 1:
    return _wrap_value_in_dict(input, props)
  if input is None or isinstance(input, float) and math.isnan(input):
    # Return empty dict for missing inputs.
    return {}
  if isinstance(input, dict) or is_primitive(input):
    raise ValueError(
      f'The input should be a list, not a primitive. '
      f'Got input type: {type(input)}, with a wrapping spec: {spec}'
    )
  res = [_wrap_in_dicts(elem, spec[1:]) for elem in cast(Iterable, input)]
  return _wrap_value_in_dict(res, props)


def wrap_in_dicts(input: Iterable[object], spec: list[PathTuple]) -> Generator:
  """Wraps an object or iterable in a dict according to the spec."""
  return (_wrap_in_dicts(elem, spec) for elem in input)


def schema_contains_path(schema: Schema, path: PathTuple) -> bool:
  """Check if a schema contains a path."""
  current_field = cast(Field, schema)
  for path_part in path:
    if path_part == PATH_WILDCARD:
      if current_field.repeated_field is None:
        return False
      current_field = current_field.repeated_field
    else:
      if current_field.fields is None or path_part not in current_field.fields:
        return False
      current_field = current_field.fields[str(path_part)]
  return True


def create_json_map_output_schema(map_schema: Field, output_path: PathTuple) -> Schema:
  """Create a json schema describing the final output of a map function."""
  json_schema = map_schema.model_copy(deep=True)
  for path_part in reversed(output_path):
    if path_part == PATH_WILDCARD:
      json_schema = Field(repeated_field=json_schema)
    else:
      json_schema = Field(fields={path_part: json_schema})

  assert json_schema.fields, 'json_schema always has fields'
  return Schema(fields=json_schema.fields)


def create_signal_schema(
  signal: Signal,
  source_path: PathTuple,
  current_schema: Schema,
  embedding_info: Optional[EmbeddingInfo] = None,
) -> Optional[Schema]:
  """Create a signal schema describing the enriched fields.

  Returns None if the signal has no predefined schema.
  """
  leafs = current_schema.leafs
  # Validate that the enrich fields are actually a valid leaf path.
  if source_path not in leafs:
    raise ValueError(f'"{source_path}" is not a valid leaf path. Leaf paths: {leafs.keys()}')

  signal_schema = signal.fields()
  if not signal_schema:
    return None

  signal_schema.signal = signal.model_dump(exclude_none=True)
  if embedding_info:
    signal_schema.embedding = embedding_info

  enriched_schema = field(fields={signal.key(is_computed_signal=True): signal_schema})

  for path_part in reversed(source_path):
    if path_part == PATH_WILDCARD:
      enriched_schema = Field(repeated_field=enriched_schema)
    else:
      enriched_schema = Field(fields={path_part: enriched_schema})

  if not enriched_schema.fields:
    raise ValueError('This should not happen since enriched_schema always has fields (see above)')

  return schema(enriched_schema.fields.copy())


def _flat_embeddings(
  input: Union[Item, Iterable[Item]], path: PathKey = ()
) -> Iterator[tuple[PathKey, list[Item]]]:
  if (
    isinstance(input, list)
    and len(input) > 0
    and isinstance(input[0], dict)
    and EMBEDDING_KEY in input[0]
  ):
    yield path, input
  elif isinstance(input, dict):
    for k, v in input.items():
      yield from _flat_embeddings(v, path)
  elif isinstance(input, list):
    for i, v in enumerate(input):
      yield from _flat_embeddings(v, (*path, i))
  else:
    # Ignore other primitives.
    pass


def write_embeddings_to_disk(
  vector_index: VectorDBIndex, signal_items: Iterable[Item], output_dir: str
) -> None:
  """Write a set of embeddings to disk."""
  path_embedding_items = (
    _flat_embeddings(signal_item, path=(signal_item[ROWID],)) for signal_item in signal_items
  )

  def _get_span_vectors() -> Iterator[Item]:
    for path_item in path_embedding_items:
      for path_key, embedding_items in path_item:
        if not path_key or not embedding_items:
          # Sparse embeddings may not have an embedding for every key.
          continue

        embedding_vectors: list[np.ndarray] = []
        spans: list[tuple[int, int]] = []

        for e in embedding_items:
          text_span = e[SPAN_KEY]
          vector = e[EMBEDDING_KEY]
          # We squeeze here because embedding functions can return outer dimensions of 1.
          embedding_vectors.append(vector.reshape(-1))
          spans.append((text_span[TEXT_SPAN_START_FEATURE], text_span[TEXT_SPAN_END_FEATURE]))

        yield (path_key, spans, embedding_vectors)

  span_vectors = _get_span_vectors()

  for span_vectors_chunk in chunks(span_vectors, EMBEDDINGS_WRITE_CHUNK_SIZE):
    chunk_spans: list[tuple[PathKey, list[tuple[int, int]]]] = []
    chunk_embedding_vectors: list[np.ndarray] = []
    for path_key, spans, vectors in span_vectors_chunk:
      chunk_spans.append((path_key, spans))
      chunk_embedding_vectors.extend(vectors)

    embedding_matrix = np.array(chunk_embedding_vectors, dtype=np.float32)

    vector_index.add(chunk_spans, embedding_matrix)
    vector_index.save(output_dir)

    del embedding_matrix, chunk_embedding_vectors, chunk_spans
    gc.collect()


def write_items_to_parquet(
  items: Iterable[Item],
  output_dir: str,
  schema: Schema,
  filename_prefix: str,
  shard_index: int,
  num_shards: int,
) -> str:
  """Write a set of items to a parquet file, in columnar format."""
  schema = schema.model_copy(deep=True)
  # Add a rowid column.
  schema.fields[ROWID] = Field(dtype=STRING)

  arrow_schema = schema_to_arrow_schema(schema)
  out_filename = get_parquet_filename(filename_prefix, shard_index, num_shards)
  filepath = os.path.join(output_dir, out_filename)
  f = open_file(filepath, mode='wb')
  writer = ParquetWriter(schema)
  writer.open(f)
  debug = env('DEBUG', False)
  num_items = 0
  for item in items:
    # Add a rowid column.
    if ROWID not in item:
      item[ROWID] = secrets.token_urlsafe(nbytes=12)  # 16 base64 characters.
    if debug:
      try:
        _validate(item, arrow_schema)
      except Exception as e:
        raise ValueError(f'Error validating item: {json.dumps(item)}') from e
    writer.write(item)
    num_items += 1
  writer.close()
  f.close()
  return out_filename


def _validate(item: Item, schema: pa.Schema) -> None:
  # Try to parse the item using the inferred schema.
  try:
    pa.RecordBatch.from_pylist([item], schema=schema)
  except pa.ArrowTypeError:
    log('Failed to parse arrow item using the arrow schema.')
    log('Item:')
    log(pprint.pformat(item, indent=2))
    log('Arrow schema:')
    log(schema)
    raise  # Re-raise the same exception, same stacktrace.


def get_parquet_filename(prefix: str, shard_index: int, num_shards: int) -> str:
  """Return the filename for a parquet file."""
  return f'{prefix}-{shard_index:05d}-of-{num_shards:05d}.parquet'


def _flatten_keys(
  rowid: str,
  nested_input: Iterable[Any],
  location: list[int],
  is_primitive_predicate: Callable[[object], bool],
) -> Iterator[VectorKey]:
  if (
    is_primitive_predicate(nested_input)
    or is_primitive(nested_input)
    or isinstance(nested_input, dict)
  ):
    yield (rowid, *location)
    return

  for i, input in enumerate(nested_input):
    yield from _flatten_keys(rowid, input, [*location, i], is_primitive_predicate)


def flatten_keys(
  rowids: Iterable[str],
  nested_input: Iterable[Any],
  is_primitive_predicate: Callable[[object], bool] = is_primitive,
) -> Iterator[Optional[PathKey]]:
  """Flatten the rowids of a nested input."""
  for rowid, input in zip(rowids, nested_input):
    if input is None:
      yield None
      continue
    yield from _flatten_keys(rowid, input, [], is_primitive_predicate)


Tin = TypeVar('Tin')
Tout = TypeVar('Tout')


def sparse_to_dense_compute(
  sparse_input: Iterator[Optional[Tin]], func: Callable[[Iterator[Tin]], Iterator[Tout]]
) -> Iterator[Optional[Tout]]:
  """Densifies the input before calling the provided `func` and sparsifies the output."""
  sparse_input = iter(sparse_input)
  sparse_input, sparse_input_2 = itertools.tee(sparse_input, 2)
  dense_input = cast(Iterator[Tin], filter(lambda x: x is not None, sparse_input_2))
  dense_output = iter(func(dense_input))
  for input in sparse_input:
    if input is None:
      yield None
    else:
      yield next(dense_output)


def shard_id_to_range(
  shard_id: Optional[int], shard_count: Optional[int], num_items: int
) -> tuple[int, int]:
  """Compute the start and end offsets for a shard."""
  shard_size = math.ceil(num_items / shard_count) if shard_count is not None else num_items
  shard_start_idx = min(shard_id * shard_size, num_items) if shard_id is not None else 0
  shard_end_idx = min((shard_id + 1) * shard_size, num_items) if shard_id is not None else num_items
  return (shard_start_idx, shard_end_idx)


def _cardinality_prefix(path: PathTuple) -> PathTuple:
  """Returns the cardinality prefix for a path."""
  # Find the last wildcard in the path.
  wildcard_idx = 0
  for i, path_part in enumerate(path):
    if path_part == PATH_WILDCARD:
      wildcard_idx = i
  return path[:wildcard_idx]


def paths_have_same_cardinality(path1: PathTuple, path2: PathTuple) -> bool:
  """Returns true if the paths have the same cardinality."""
  return _cardinality_prefix(path1) == _cardinality_prefix(path2)


def get_sibling_output_path(path: PathTuple, suffix: str) -> PathTuple:
  """Get the output path for a sibling column."""
  # Find the last non-wildcard in the path.
  index = 0
  for i, path_part in enumerate(path):
    if path_part != PATH_WILDCARD:
      index = i
  return (*path[:index], f'{path[index]}__{suffix}', *path[index + 1 :])


def get_common_ancestor(path1: PathTuple, path2: PathTuple) -> tuple[PathTuple, str, str]:
  """Get the path of the common ancestor of the two paths, along with the columns of the paths."""
  index = 0
  column1: str = ''
  column2: str = ''
  for i, (path_part1, path_part2) in enumerate(zip(path1, path2)):
    if path_part1 != path_part2:
      index = i
      column1 = path_part1
      column2 = path_part2
      break
  ancestor_path = path1[:index]
  return (ancestor_path, column1, column2)


def get_callable_name(map_fn: MapFn) -> str:
  """Get the name of a callable function."""
  if hasattr(map_fn, '__name__'):
    return map_fn.__name__
  if isinstance(map_fn, partial):
    return get_callable_name(map_fn.func)
  if hasattr(map_fn, 'name'):
    return getattr(map_fn, 'name')
  return 'unknown'
