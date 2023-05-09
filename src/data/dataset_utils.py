"""Utilities for working with datasets."""

import math
import os
import pprint
import secrets
from collections.abc import Iterable
from typing import Any, Callable, Generator, Iterator, Optional, Sequence, TypeVar, Union, cast

import numpy as np
import pyarrow as pa
from pydantic import BaseModel

from ..parquet_writer import ParquetWriter
from ..schema import (
  SIGNAL_METADATA_KEY,
  TEXT_SPAN_END_FEATURE,
  TEXT_SPAN_START_FEATURE,
  VALUE_KEY,
  LILAC_COLUMN,
  PATH_WILDCARD,
  UUID_COLUMN,
  Field,
  Item,
  ItemValue,
  PathTuple,
  Schema,
  field,
  schema,
  schema_to_arrow_schema,
)
from ..signals.signal import Signal
from ..utils import file_exists, log, open_file

NP_INDEX_KEYS_KWD = 'keys'
NP_EMBEDDINGS_KWD = 'embeddings'


def is_primitive(obj: object) -> bool:
  """Returns True if the object is a primitive."""
  if isinstance(obj, (str, bytes, np.ndarray)):
    return True
  if isinstance(obj, Iterable):
    return False
  return True


def _replace_embeddings_with_none(input: Union[Item, ItemValue]) -> Union[Item, ItemValue]:
  if isinstance(input, np.ndarray):
    return None
  if isinstance(input, dict):
    return {k: _replace_embeddings_with_none(v) for k, v in input.items()}
  if isinstance(input, list):
    return [_replace_embeddings_with_none(v) for v in input]

  return input


def replace_embeddings_with_none(input: Union[Item, ItemValue]) -> Item:
  """Replaces all embeddings with None."""
  return cast(Item, _replace_embeddings_with_none(input))


def _wrap_primitive_values(input: Union[Item, ItemValue]) -> Union[Item, ItemValue]:
  if isinstance(input, dict):
    # Wrap all the values of the dictionary in {__value__: value} if it is not already wrapped and
    # it is not a UUID.
    return {
      k: _wrap_primitive_values(v) if k not in (VALUE_KEY, UUID_COLUMN) else v
      for k, v in input.items()
    }
  elif isinstance(input, list):
    return [_wrap_primitive_values(v) for v in input]

  if input is None:
    # We don't wrap None values with value key to keep sparsity.
    return None
  return {VALUE_KEY: input}


def lilac_items(items: Iterable[Item]) -> Iterable[Item]:
  """A util for testing that converts items to their primitive wrapped items."""
  if isinstance(items, (list, Sequence)):
    return [cast(Item, _wrap_primitive_values(item)) for item in items]
  return (cast(Item, _wrap_primitive_values(item)) for item in items)


def lilac_item(value: Optional[ItemValue] = None,
               metadata: Optional[dict[str, Union[Item, ItemValue]]] = None,
               allow_none_value: Optional[bool] = False) -> Item:
  """Wrap a value in a dict with the value key."""
  out_item: Item = {}
  if value is not None or allow_none_value:
    out_item[VALUE_KEY] = value
  if metadata:
    out_item.update(cast(dict, _wrap_primitive_values(metadata)))
  return out_item


def signal_item(value: Optional[ItemValue] = None,
                metadata: Optional[dict[str, Union[Item, ItemValue]]] = None) -> Item:
  """Returns a signal item given signal metadata."""
  signal_metadata: Optional[dict[str, Union[Item, ItemValue]]] = None
  if metadata:
    signal_metadata = {SIGNAL_METADATA_KEY: metadata}
  return lilac_item(value, signal_metadata)


def lilac_span(start: int,
               end: int,
               metadata: Optional[dict[str, Union[Item, ItemValue]]] = None) -> Item:
  """Wrap a value in a dict with the value key."""
  return signal_item(lilac_span_value(start, end), metadata)


def lilac_span_value(start: int, end: int) -> Item:
  """The lilac span value.

  This is useful if you want to use span_value with signal_item, for unit tests.
  """
  return {TEXT_SPAN_START_FEATURE: start, TEXT_SPAN_END_FEATURE: end}


def lilac_embedding(embedding: np.ndarray,
                    metadata: Optional[dict[str, Union[Item, ItemValue]]] = {}) -> Item:
  """Wrap a value in a dict with the value key."""
  return signal_item(embedding, metadata)


Tflatten = TypeVar('Tflatten', object, np.ndarray)


def _flatten(input: Union[Iterable, object], is_primitive_predicate: Callable[[object],
                                                                              bool]) -> Generator:
  """Flattens a nested iterable."""
  if is_primitive_predicate(input):
    yield input
  elif is_primitive(input):
    pass
  else:
    for elem in cast(Iterable, input):
      if isinstance(elem, dict):
        yield from _flatten(elem.values(), is_primitive_predicate)
      else:
        yield from _flatten(elem, is_primitive_predicate)


def flatten(input: Union[Iterable, Tflatten],
            is_primitive_predicate: Callable[[object], bool] = is_primitive) -> list[Tflatten]:
  """Flattens a nested iterable."""
  return list(_flatten(input, is_primitive_predicate))


def _wrap_value_in_dict(input: Union[object, dict], props: PathTuple) -> Union[object, dict]:
  # If the signal produced no value, or nan, we should return None so the parquet value is sparse.
  if isinstance(input, float) and math.isnan(input):
    input = None
  for prop in reversed(props):
    input = {prop: input}
  return input


def _unflatten(flat_input: Iterator[list[object]],
               original_input: Union[Iterable, object]) -> Union[list, dict]:
  """Unflattens a flattened iterable according to the original iterable's structure."""
  if is_primitive(original_input):
    return next(flat_input)
  else:
    values: Iterable
    if isinstance(original_input, dict):
      values = original_input.values()
    else:
      values = cast(Iterable, original_input)
    return [_unflatten(flat_input, orig_elem) for orig_elem in values]


def unflatten(flat_input: Iterable, original_input: Union[Iterable, object]) -> list:
  """Unflattens a flattened iterable according to the original iterable's structure."""
  return cast(list, _unflatten(iter(flat_input), original_input))


def _wrap_in_dicts(input: Union[object, Iterable[object]],
                   spec: list[PathTuple]) -> Union[object, Iterable[object]]:
  """Wraps an object or iterable in a dict according to the spec."""
  props = spec[0] if spec else tuple()
  if len(spec) == 1:
    return _wrap_value_in_dict(input, props)
  if input is None:
    return {}
  res = [_wrap_in_dicts(elem, spec[1:]) for elem in cast(Iterable, input)]
  return _wrap_value_in_dict(res, props)


def wrap_in_dicts(input: Iterable[object], spec: list[PathTuple]) -> Iterable[object]:
  """Wraps an object or iterable in a dict according to the spec."""
  return [_wrap_in_dicts(elem, spec) for elem in input]


def _merge_field_into(schema: Field, destination: Field) -> None:
  if isinstance(schema, Field):
    destination.signal_root = destination.signal_root or schema.signal_root
    destination.dtype = destination.dtype or schema.dtype
  if schema.fields:
    if destination.fields is None:
      raise ValueError('Failed to merge schemas. Origin schema has fields but destination does not')
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


def merge_schemas(schemas: list[Schema]) -> Schema:
  """Merge a list of schemas."""
  merged_schema = Schema(fields={})
  for s in schemas:
    _merge_field_into(cast(Field, s), cast(Field, merged_schema))
  return merged_schema


def schema_contains_path(schema: Schema, path: PathTuple) -> bool:
  """Check if a schema contains a path."""
  # Remove the value key from the end of the path as it's not directly in the schema, but users can
  # query this path.
  if path[-1] == VALUE_KEY:
    path = path[:-1]

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


def path_is_from_lilac(path: PathTuple) -> bool:
  """Check if a path is from lilac."""
  return path[0] == LILAC_COLUMN


def create_signal_schema(signal: Signal, source_path: PathTuple, current_schema: Schema) -> Schema:
  """Create a schema describing the enriched fields added an enrichment."""
  leafs = current_schema.leafs
  # Validate that the enrich fields are actually a valid leaf path.
  if source_path not in leafs:
    raise ValueError(f'"{source_path}" is not a valid leaf path. '
                     f'Leaf paths: {leafs.keys()}')

  signal_schema = signal.fields()
  signal_schema.signal_root = True

  enriched_schema = field({signal.key(): signal_schema})

  for path_part in reversed(source_path):
    if path_part == PATH_WILDCARD:
      enriched_schema = Field(repeated_field=enriched_schema)
    else:
      enriched_schema = Field(fields={path_part: enriched_schema})

  if not enriched_schema.fields:
    raise ValueError('This should not happen since enriched_schema always has fields (see above)')

  # If a signal is enriching output of a signal, skip the lilac prefix to avoid double prefixing.
  if path_is_from_lilac(source_path):
    enriched_schema = enriched_schema.fields[LILAC_COLUMN]

  return schema({UUID_COLUMN: 'string', LILAC_COLUMN: enriched_schema})


def write_embeddings_to_disk(keys: Iterable[str], embeddings: Iterable[object], output_dir: str,
                             filename_prefix: str, shard_index: int, num_shards: int) -> str:
  """Write a set of embeddings to disk."""
  out_filename = embedding_index_filename(filename_prefix, shard_index, num_shards)
  index_path = os.path.join(output_dir, out_filename)

  # Restrict the keys to only those that are embeddings.
  def embedding_predicate(input: Any) -> bool:
    return isinstance(input, np.ndarray)

  flat_keys = flatten_keys(keys, embeddings, is_primitive_predicate=embedding_predicate)
  flat_embeddings = np.array(flatten(embeddings, is_primitive_predicate=embedding_predicate))

  # Write the embedding index and the ordered UUID column to disk so they can be joined later.
  np_keys = np.empty(len(flat_keys), dtype=object)
  np_keys[:] = flat_keys

  with open_file(index_path, 'wb') as f:
    np.savez(f, **{NP_INDEX_KEYS_KWD: np_keys, NP_EMBEDDINGS_KWD: flat_embeddings})

  return out_filename


class EmbeddingIndex(BaseModel):
  """The result of an embedding index query."""

  class Config:
    arbitrary_types_allowed = True

  keys: list[PathTuple]
  embeddings: np.ndarray


def read_embedding_index(output_dir: str, filename: str) -> EmbeddingIndex:
  """Reads the embedding index for a column from disk."""
  index_path = os.path.join(output_dir, filename)

  if not file_exists(index_path):
    raise ValueError(F'Embedding index does not exist at path {index_path}. '
                     'Please run db.compute_signal() on the embedding signal first.')

  # Read the embedding index from disk.
  with open_file(index_path, 'rb') as f:
    np_index: dict[str, np.ndarray] = np.load(f, allow_pickle=True)
    embeddings = np_index[NP_EMBEDDINGS_KWD]
    index_keys = np_index[NP_INDEX_KEYS_KWD].tolist()
  return EmbeddingIndex(path=index_path, keys=index_keys, embeddings=embeddings)


def write_items_to_parquet(out_items: Iterable[Item],
                           output_dir: str,
                           schema: Schema,
                           filename_prefix: str,
                           shard_index: int,
                           num_shards: int,
                           dont_wrap_primitives: Optional[bool] = False) -> tuple[str, int]:
  """Write a set of items to a parquet file, in columnar format."""
  if not dont_wrap_primitives:
    out_items = lilac_items(out_items)

  arrow_schema = schema_to_arrow_schema(schema)
  out_filename = parquet_filename(filename_prefix, shard_index, num_shards)
  filepath = os.path.join(output_dir, out_filename)
  f = open_file(filepath, mode='wb')
  writer = ParquetWriter(schema)
  writer.open(f)
  num_items = 0
  for item in out_items:
    # Add a UUID column.
    if UUID_COLUMN not in item:
      item[UUID_COLUMN] = secrets.token_urlsafe(nbytes=12)  # 16 base64 characters.
    if os.getenv('DEBUG'):
      _validate(item, arrow_schema)
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
                  is_primitive_predicate: Callable[[object], bool]) -> list[PathTuple]:
  if is_primitive_predicate(nested_input):
    return [(uuid, *location)]
  elif is_primitive(nested_input):
    return []
  else:
    result: list[PathTuple] = []
    if isinstance(nested_input, dict):
      for value in nested_input.values():
        result.extend(_flatten_keys(uuid, value, location, is_primitive_predicate))
    else:
      for i, input in enumerate(nested_input):
        result.extend(_flatten_keys(uuid, input, [*location, i], is_primitive_predicate))
    return result


def flatten_keys(
    uuids: Iterable[str],
    nested_input: Iterable,
    is_primitive_predicate: Callable[[object], bool] = is_primitive) -> list[PathTuple]:
  """Flatten the uuid keys of a nested input."""
  result: list[PathTuple] = []
  for uuid, input in zip(uuids, nested_input):
    result.extend(_flatten_keys(uuid, input, [], is_primitive_predicate))
  return result


def embedding_index_filename(prefix: str, shard_index: int, num_shards: int) -> str:
  """Return the filename for the embedding index."""
  return f'{prefix}-{shard_index:05d}-of-{num_shards:05d}.npy'
