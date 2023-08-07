"""Utilities for working with datasets."""

import json
import math
import os
import pickle
import pprint
import secrets
from collections.abc import Iterable
from typing import Any, Callable, Iterator, Optional, Sequence, TypeVar, Union, cast

import numpy as np
import pyarrow as pa

from ..batch_utils import deep_flatten
from ..env import env
from ..parquet_writer import ParquetWriter
from ..schema import (
  EMBEDDING_KEY,
  PATH_WILDCARD,
  TEXT_SPAN_END_FEATURE,
  TEXT_SPAN_START_FEATURE,
  UUID_COLUMN,
  VALUE_KEY,
  Field,
  Item,
  PathKey,
  PathTuple,
  Schema,
  VectorKey,
  field,
  schema,
  schema_to_arrow_schema,
)
from ..signals.signal import Signal
from ..utils import file_exists, is_primitive, log, open_file

_SPANS_SUFFIX = '.spans.pkl'
_EMBEDDINGS_SUFFIX = '.npy'


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


def count_primitives(input: Union[Iterable, Iterator]) -> int:
  """Iterate through each element of the input, flattening each one, computing a count.

  Sum the final set of counts. This is the important iterable not to exhaust.
  """
  return sum((len(list(deep_flatten(i))) for i in input))


def _wrap_value_in_dict(input: Union[object, dict], props: PathTuple) -> Union[object, dict]:
  # If the signal produced no value, or nan, we should return None so the parquet value is sparse.
  if isinstance(input, float) and math.isnan(input):
    input = None
  for prop in reversed(props):
    input = {prop: input}
  return input


def _wrap_in_dicts(input: Union[object, Iterable[object]],
                   spec: list[PathTuple]) -> Union[object, Iterable[object]]:
  """Wraps an object or iterable in a dict according to the spec."""
  props = spec[0] if spec else tuple()
  if len(spec) == 1:
    return _wrap_value_in_dict(input, props)
  if input is None or isinstance(input, float) and math.isnan(input):
    # Return empty dict for missing inputs.
    return {}
  res = [_wrap_in_dicts(elem, spec[1:]) for elem in cast(Iterable, input)]
  return _wrap_value_in_dict(res, props)


def wrap_in_dicts(input: Iterable[object], spec: list[PathTuple]) -> Iterable[object]:
  """Wraps an object or iterable in a dict according to the spec."""
  return [_wrap_in_dicts(elem, spec) for elem in input]


def _merge_field_into(schema: Field, destination: Field) -> None:
  if isinstance(schema, Field):
    destination.signal = destination.signal or schema.signal
    destination.dtype = destination.dtype or schema.dtype
  if schema.fields:
    destination.fields = destination.fields or {}
    for field_name, subfield in schema.fields.items():
      if field_name not in destination.fields:
        destination.fields[field_name] = subfield.copy(deep=True)
      else:
        _merge_field_into(subfield, destination.fields[field_name])
  elif schema.repeated_field:
    if not destination.repeated_field:
      raise ValueError('Failed to merge schemas. Origin schema is repeated, but destination is not')
    _merge_field_into(schema.repeated_field, destination.repeated_field)
  else:
    if destination.dtype != schema.dtype:
      raise ValueError(f'Failed to merge schemas. Origin schema has dtype {schema.dtype}, '
                       f'but destination has dtype {destination.dtype}')


def merge_schemas(schemas: Sequence[Union[Schema, Field]]) -> Schema:
  """Merge a list of schemas."""
  merged_schema = Schema(fields={})
  for s in schemas:
    _merge_field_into(cast(Field, s), cast(Field, merged_schema))
  return merged_schema


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


def create_signal_schema(signal: Signal, source_path: PathTuple, current_schema: Schema) -> Schema:
  """Create a schema describing the enriched fields added an enrichment."""
  leafs = current_schema.leafs
  # Validate that the enrich fields are actually a valid leaf path.
  if source_path not in leafs:
    raise ValueError(f'"{source_path}" is not a valid leaf path. Leaf paths: {leafs.keys()}')

  signal_schema = signal.fields()
  signal_schema.signal = signal.dict()

  enriched_schema = field(fields={signal.key(is_computed_signal=True): signal_schema})

  for path_part in reversed(source_path):
    if path_part == PATH_WILDCARD:
      enriched_schema = Field(repeated_field=enriched_schema)
    else:
      enriched_schema = Field(fields={path_part: enriched_schema})

  if not enriched_schema.fields:
    raise ValueError('This should not happen since enriched_schema always has fields (see above)')

  return schema({UUID_COLUMN: 'string', **cast(dict, enriched_schema.fields)})


def write_embeddings_to_disk(uuids: Iterable[str], signal_items: Iterable[Item], output_dir: str,
                             shard_index: int, num_shards: int) -> str:
  """Write a set of embeddings to disk."""
  output_path_prefix = embedding_index_filename_prefix(output_dir, shard_index, num_shards)

  # For each item, we have a list of embedding spans.
  def embedding_predicate(input: Any) -> bool:
    return (isinstance(input, list) and len(input) > 0 and isinstance(input[0], dict) and
            EMBEDDING_KEY in input[0])

  path_keys = flatten_keys(uuids, signal_items, is_primitive_predicate=embedding_predicate)
  all_embeddings = cast(Iterable[Item],
                        deep_flatten(signal_items, is_primitive_predicate=embedding_predicate))

  embedding_vectors: list[np.ndarray] = []
  all_spans: list[tuple[PathKey, list[tuple[int, int]]]] = []
  for path_key, embeddings in zip(path_keys, all_embeddings):
    if not path_key or not embeddings:
      # Sparse embeddings may not have an embedding for every key.
      continue

    spans: list[tuple[int, int]] = []
    for e in embeddings:
      span = e[VALUE_KEY]
      vector = e[EMBEDDING_KEY]
      # We squeeze here because embedding functions can return outer dimensions of 1.
      embedding_vectors.append(vector.reshape(-1))
      spans.append((span[TEXT_SPAN_START_FEATURE], span[TEXT_SPAN_END_FEATURE]))
    all_spans.append((path_key, spans))

  embedding_matrix = np.array(embedding_vectors)
  # Write the embedding index and the ordered UUID column to disk so they can be joined later.

  with open_file(output_path_prefix + _EMBEDDINGS_SUFFIX, 'wb') as f:
    np.save(cast(str, f), embedding_matrix, allow_pickle=False)
  with open_file(output_path_prefix + _SPANS_SUFFIX, 'wb') as f:
    pickle.dump(all_spans, f)

  return output_path_prefix


def read_embeddings_from_disk(
    filepath_prefix: str) -> tuple[list[tuple[PathKey, list[tuple[int, int]]]], np.ndarray]:
  """Reads the embeddings from disk."""
  if not file_exists(filepath_prefix + _EMBEDDINGS_SUFFIX):
    raise ValueError(F'Embedding index does not exist at path {filepath_prefix}. '
                     'Please run dataset.compute_signal() on the embedding signal first.')
  # Read the embedding index from disk.
  embeddings = np.load(filepath_prefix + _EMBEDDINGS_SUFFIX, allow_pickle=False)
  with open_file(filepath_prefix + _SPANS_SUFFIX, 'rb') as f:
    spans: list[tuple[PathKey, list[tuple[int, int]]]] = pickle.load(f)
  return spans, embeddings


def write_items_to_parquet(items: Iterable[Item], output_dir: str, schema: Schema,
                           filename_prefix: str, shard_index: int,
                           num_shards: int) -> tuple[str, int]:
  """Write a set of items to a parquet file, in columnar format."""
  arrow_schema = schema_to_arrow_schema(schema)
  out_filename = parquet_filename(filename_prefix, shard_index, num_shards)
  filepath = os.path.join(output_dir, out_filename)
  f = open_file(filepath, mode='wb')
  writer = ParquetWriter(schema)
  writer.open(f)
  debug = env('DEBUG', False)
  num_items = 0
  for item in items:
    # Add a UUID column.
    if UUID_COLUMN not in item:
      item[UUID_COLUMN] = secrets.token_urlsafe(nbytes=12)  # 16 base64 characters.
    if debug:
      try:
        _validate(item, arrow_schema)
      except Exception as e:
        raise ValueError(f'Error validating item: {json.dumps(item)}') from e
    writer.write(item)
    num_items += 1
  writer.close()
  f.close()
  return out_filename, num_items


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


def parquet_filename(prefix: str, shard_index: int, num_shards: int) -> str:
  """Return the filename for a parquet file."""
  return f'{prefix}-{shard_index:05d}-of-{num_shards:05d}.parquet'


def _flatten_keys(uuid: str, nested_input: Iterable, location: list[int],
                  is_primitive_predicate: Callable[[object], bool]) -> Iterator[VectorKey]:
  if is_primitive_predicate(nested_input) or is_primitive(nested_input) or isinstance(
      nested_input, dict):
    yield (uuid, *location)
    return

  for i, input in enumerate(nested_input):
    yield from _flatten_keys(uuid, input, [*location, i], is_primitive_predicate)


def flatten_keys(
    uuids: Iterable[str],
    nested_input: Iterable,
    is_primitive_predicate: Callable[[object],
                                     bool] = is_primitive) -> Iterator[Optional[VectorKey]]:
  """Flatten the uuid keys of a nested input."""
  for uuid, input in zip(uuids, nested_input):
    if input is None:
      yield None
      continue
    yield from _flatten_keys(uuid, input, [], is_primitive_predicate)


def embedding_index_filename_prefix(output_dir: str, shard_index: int, num_shards: int) -> str:
  """Return the filename prefix for the embedding index."""
  npy_filename = f'embeddings-{shard_index:05d}-of-{num_shards:05d}'
  return os.path.join(output_dir, npy_filename)


Tin = TypeVar('Tin')
Tout = TypeVar('Tout')


def sparse_to_dense_compute(
    sparse_input: Iterator[Optional[Tin]],
    func: Callable[[Iterable[Tin]], Iterable[Tout]]) -> Iterator[Optional[Tout]]:
  """Densifies the input before calling the provided `func` and sparsifies the output."""
  locations: list[int] = []
  total_size: int = 0

  def densify(x: Iterator[Optional[Tin]]) -> Iterator[Tin]:
    nonlocal locations, total_size
    for i, value in enumerate(x):
      total_size += 1
      if value is not None:
        locations.append(i)
        yield value

  dense_input = densify(sparse_input)
  dense_output = iter(func(dense_input))
  index = 0

  location_index = 0

  while True:
    try:
      out = next(dense_output)
      out_index = locations[location_index]
      while index < out_index:
        yield None
        index += 1
      yield out
      location_index += 1
      index += 1
    except StopIteration:
      while index < total_size:
        yield None
        index += 1
      return
