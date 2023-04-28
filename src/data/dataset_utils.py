"""Utilities for working with datasets."""

from collections.abc import Iterable
from typing import Generator, Iterator, Optional, Sequence, Union, cast

from ..schema import (
    PATH_WILDCARD,
    UUID_COLUMN,
    DataType,
    Field,
    Item,
    Path,
    PathTuple,
    Schema,
    SignalOut,
    normalize_path,
)
from ..signals.signal import Signal


def replace_repeated_wildcards(path: Path, path_repeated_idxs: Optional[list[int]]) -> Path:
  """Replace the repeated wildcards in a path with the repeated indexes."""
  if path_repeated_idxs is None:
    # No repeated indexes, so just return the path.
    return path

  replaced_path: list[Union[str, int]] = []
  path_repeated_idx_i = 0
  for path_part in path:
    # Replace wildcards with the actual index.
    if path_part == PATH_WILDCARD:
      replaced_path.append(path_repeated_idxs[path_repeated_idx_i])
      path_repeated_idx_i += 1
    else:
      replaced_path.append(path_part)

  return tuple(replaced_path)


def is_primitive(obj: object) -> bool:
  """Returns True if the object is an iterable but not a string or bytes."""
  return not isinstance(obj, Iterable) or isinstance(obj, (str, bytes))


def _flatten(input: Union[Iterable, object]) -> Generator:
  """Flattens a nested iterable."""
  if is_primitive(input):
    yield input
  else:
    for elem in cast(Iterable, input):
      yield from _flatten(elem)


def flatten(input: Union[Iterable, object]) -> list[object]:
  """Flattens a nested iterable."""
  return list(_flatten(input))


def _unflatten(flat_input: Iterator[list[object]], original_input: Union[Iterable, object]) -> list:
  """Unflattens a flattened iterable according to the original iterable's structure."""
  if is_primitive(original_input):
    return next(flat_input)
  else:
    return [_unflatten(flat_input, orig_elem) for orig_elem in cast(Iterable, original_input)]


def unflatten(flat_input: Iterable, original_input: Union[Iterable, object]) -> list:
  """Unflattens a flattened iterable according to the original iterable's structure."""
  return _unflatten(iter(flat_input), original_input)


def make_enriched_items(source_path: Path, row_ids: Sequence[str], signal: Signal,
                        leaf_items: Iterable[Optional[SignalOut]],
                        repeated_idxs: Iterable[Optional[list[int]]]) -> Iterable[Item]:
  """Make enriched items from leaf items and a path. This is used by both signals and splitters.

  NOTE: The iterables that are passed in are not 1:1 with row_ids. The logic of this method will
  merge the same UUIDs as long as they are contiguous.
  """
  working_enriched_item: Item = {}
  num_outputs = 0
  outputs_per_key = 0

  last_row_id: Optional[str] = None
  for row_id, leaf_item, path_repeated_idxs in zip(row_ids, leaf_items, repeated_idxs):
    leaf_item = {signal.name: leaf_item}
    num_outputs += 1

    # Duckdb currently just returns a single int as that's all we support. The rest of the code
    # supports arrays, so we make it an array for the future when duckdb gives us a list of indices.
    if isinstance(path_repeated_idxs, int):
      path_repeated_idxs = [path_repeated_idxs]

    if last_row_id is None:
      last_row_id = row_id
      working_enriched_item = {UUID_COLUMN: row_id}

    # When we're at a new row_id, yield the last working item.
    if last_row_id != row_id:
      if outputs_per_key > 0:
        yield working_enriched_item
      last_row_id = row_id
      working_enriched_item = {UUID_COLUMN: row_id}
      outputs_per_key = 0

    if not leaf_item:
      continue

    # Tracking outputs per key allows us to know if we have a sparse output so it will not be
    # yielded at all.
    outputs_per_key += 1

    # Apply the list of path indices to the path to replace wildcards.
    resolved_path = replace_repeated_wildcards(
        path=source_path, path_repeated_idxs=path_repeated_idxs)

    # Now that we have resolves indices, we can modify the enriched item.
    enrich_item_from_leaf_item(
        enriched_item=working_enriched_item, path=resolved_path, leaf_item=leaf_item)

  if num_outputs != len(row_ids):
    raise ValueError(
        f'The enriched outputs ({num_outputs}) and the input data ({len(row_ids)}) do not have the '
        'same length. This means the enricher either didnt generate a "None" for a sparse output, '
        'or generated too many items.')

  if outputs_per_key > 0:
    yield working_enriched_item


def enrich_item_from_leaf_item(enriched_item: Item, path: Path, leaf_item: SignalOut) -> None:
  """Create an enriched item with the same hierarchy as the source."""
  path = normalize_path(path)

  enriched_subitem = enriched_item
  for i in range(len(path) - 1):
    path_component = path[i]
    next_path_component = path[i + 1]
    if isinstance(path_component, str):
      if path_component not in enriched_subitem:
        if isinstance(next_path_component, str):
          enriched_subitem[path_component] = {}
        else:
          # This needs to be filled to the length of the index. Since this is the first time we've
          # seen path_component, we can fill it exactly to the index we're going to inject.
          enriched_subitem[path_component] = [None] * (next_path_component + 1)
      else:
        if isinstance(next_path_component, int):
          # We may need to extend the length so we can write the new index.
          cur_len = len(enriched_subitem[path_component])  # type: ignore
          if cur_len <= next_path_component:
            enriched_subitem[path_component].extend(  # type: ignore
                [None] * (next_path_component - cur_len + 1))
    elif isinstance(path_component, int):
      # The nested list of nones above will fill in integer indices.
      if isinstance(next_path_component, str):
        enriched_subitem[path_component] = {}  # type: ignore
      elif isinstance(next_path_component, int):
        enriched_subitem[path_component] = []  # type: ignore
    else:
      raise ValueError(f'Unknown type {type(path_component)} in path {path}.')
    enriched_subitem = enriched_subitem[path_component]  # type: ignore

  enriched_subitem[path[-1]] = leaf_item  # type: ignore


def merge_schema_into(schema: Field, destination: Field) -> None:
  """Merges two schemas."""
  if schema.fields:
    if not destination.fields:
      raise ValueError('should not happen')
    for field_name, subfield in schema.fields.items():
      # Do not merge UUID columns.
      if field_name == UUID_COLUMN:
        continue
      if field_name not in destination.fields:
        destination.fields[field_name] = subfield
      else:
        merge_schema_into(destination.fields[field_name], subfield)
  elif schema.repeated_field:
    if not destination.repeated_field:
      raise ValueError('should not happen')
    merge_schema_into(destination.repeated_field, schema.repeated_field)
  else:
    if destination.dtype != schema.dtype:
      raise ValueError('should not happen')


def create_signal_schema(signal: Signal, source_path: PathTuple, schema: Schema) -> Schema:
  """Create a schema describing the enriched fields added an enrichment."""
  source_leafs = schema.leafs
  # Validate that the enrich fields are actually a valid leaf path.
  if source_path not in source_leafs:
    raise ValueError(f'"{source_path}" is not a valid leaf path. '
                     f'Leaf paths: {source_leafs.keys()}')

  enriched_schema = Field(fields={signal.name: signal.fields()})
  # Apply the "derived_from" field lineage to the field we are enriching.
  enriched_schema = apply_field_lineage(enriched_schema, source_path)

  for path_part in reversed(source_path):
    if path_part == PATH_WILDCARD:
      enriched_schema = Field(repeated_field=enriched_schema)
    else:
      enriched_schema = Field(fields={path_part: enriched_schema})

  if not enriched_schema.fields:
    raise ValueError('This should not happen')

  # Add the UUID column to the schema.
  enriched_schema.fields[UUID_COLUMN] = Field(dtype=DataType.STRING)
  return Schema(fields=enriched_schema.fields)


def apply_field_lineage(field: Field, derived_from: PathTuple) -> Field:
  """Returns a new field with the derived_from field set recursively on all children."""
  if field.dtype == DataType.STRING_SPAN:
    # String spans act as leafs.
    pass
  elif field.fields:
    for name, child_field in field.fields.items():
      field.fields[name] = apply_field_lineage(field.fields[name], derived_from)
  elif field.repeated_field:
    field.repeated_field = apply_field_lineage(field.repeated_field, derived_from)

  field.derived_from = derived_from
  return field


def get_field_if_exists(schema: Schema, path: Path) -> Optional[Field]:
  """Return a field from a path if it exists in the schema."""
  # Wrap in a field for convenience.
  field = cast(Field, schema)
  for path_part in path:
    if isinstance(path_part, int) or path_part == PATH_WILDCARD:
      if not field.repeated_field:
        return None
      field = field.repeated_field
    elif isinstance(path_part, str):
      if not field.fields:
        return None
      if path_part not in cast(dict, field.fields):
        return None
      field = field.fields[path_part]
  return field
