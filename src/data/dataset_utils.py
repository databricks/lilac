"""Utilities for working with datasets."""

from collections.abc import Iterable
from typing import Generator, Iterator, Union, cast

from ..schema import (
    ENTITY_FEATURE_KEY,
    LILAC_COLUMN,
    PATH_WILDCARD,
    UUID_COLUMN,
    DataType,
    Field,
    PathTuple,
    Schema,
)
from ..signals.signal import Signal


def is_primitive(obj: object) -> bool:
  """Returns True if the object is a primitive."""
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


def _wrap_value_in_dict(input: Union[object, dict], props: PathTuple) -> Union[object, dict]:
  for prop in reversed(props):
    input = {prop: input}
  return input


def _unflatten(flat_input: Iterator[list[object]],
               original_input: Union[Iterable, object]) -> Union[list, dict]:
  """Unflattens a flattened iterable according to the original iterable's structure."""
  if is_primitive(original_input):
    return next(flat_input)
  else:
    return [_unflatten(flat_input, orig_elem) for orig_elem in cast(Iterable, original_input)]


def unflatten(flat_input: Iterable, original_input: Union[Iterable, object]) -> list:
  """Unflattens a flattened iterable according to the original iterable's structure."""
  return cast(list, _unflatten(iter(flat_input), original_input))


def wrap_in_dicts(input: Union[object, Iterable[object]],
                  spec: list[PathTuple]) -> Iterable[object]:
  """Wraps an object or iterable in a dict according to the spec."""
  props = spec[0] if spec else tuple()
  if is_primitive(input) or isinstance(input, dict):
    return cast(Iterable, _wrap_value_in_dict(input, props))
  else:
    return [
        _wrap_value_in_dict(wrap_in_dicts(elem, spec[1:]), props) for elem in cast(Iterable, input)
    ]


def _merge_field_into(schema: Field, destination: Field) -> None:
  if isinstance(schema, Field):
    destination.is_entity = destination.is_entity or schema.is_entity
    destination.derived_from = destination.derived_from or schema.derived_from
    destination.signal_root = destination.signal_root or schema.signal_root
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
  for schema in schemas:
    _merge_field_into(cast(Field, schema), cast(Field, merged_schema))
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


def path_is_from_lilac(path: PathTuple) -> bool:
  """Check if a path is from lilac."""
  return path[0] == LILAC_COLUMN


def create_signal_schema(signal: Signal, source_path: PathTuple, schema: Schema) -> Schema:
  """Create a schema describing the enriched fields added an enrichment."""
  leafs = schema.leafs
  # Validate that the enrich fields are actually a valid leaf path.
  if source_path not in leafs:
    raise ValueError(f'"{source_path}" is not a valid leaf path. '
                     f'Leaf paths: {leafs.keys()}')

  signal_schema = signal.fields()
  signal_schema.signal_root = True

  # Apply the "derived_from" field lineage to the field we are enriching.
  _apply_field_lineage(signal_schema, source_path)
  enriched_schema = Field(fields={signal.key(): signal_schema})

  # If we are enriching an entity we should store the signal data in the entity field's parent.
  if source_path[-1] == ENTITY_FEATURE_KEY:
    source_path = source_path[:-1]
    enriched_schema.derived_from = schema.get_field(source_path).derived_from

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

  return Schema(fields={UUID_COLUMN: Field(dtype=DataType.STRING), LILAC_COLUMN: enriched_schema})


def _apply_field_lineage(field: Field, derived_from: PathTuple) -> None:
  """Returns a new field with the derived_from field set recursively on all children."""
  if field.dtype == DataType.STRING_SPAN:
    # String spans act as leafs.
    pass
  elif field.fields:
    for child_field in field.fields.values():
      _apply_field_lineage(child_field, derived_from)
  elif field.repeated_field:
    _apply_field_lineage(field.repeated_field, derived_from)

  field.derived_from = derived_from
