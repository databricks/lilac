"""Tests for item.py."""

import pyarrow as pa
import pytest

from .schema import (
  PATH_WILDCARD,
  DataType,
  Field,
  Item,
  Schema,
  arrow_schema_to_schema,
  child_item_from_column_path,
  column_paths_match,
  schema_to_arrow_schema,
)

NESTED_TEST_SCHEMA = Schema(
  fields={
    'person': Field(
      fields={
        'name': Field(dtype=DataType.STRING),
        'last_name': Field(dtype=DataType.STRING_SPAN, derived_from=('person', 'name')),
        # Contains a double nested array of primitives.
        'data': Field(repeated_field=Field(repeated_field=Field(dtype=DataType.FLOAT32)))
      }),
    'addresses': Field(
      repeated_field=Field(
        fields={
          'city': Field(dtype=DataType.STRING),
          'zipcode': Field(dtype=DataType.INT16),
          'current': Field(dtype=DataType.BOOLEAN),
          'locations': Field(
            repeated_field=Field(fields={
              'latitude': Field(dtype=DataType.FLOAT16),
              'longitude': Field(dtype=DataType.FLOAT64)
            }))
        })),
    'blob': Field(dtype=DataType.BINARY)
  })
NESTED_TEST_ITEM: Item = {
  'person': {
    'name': 'Test Name',
    'last_name': (5, 9)
  },
  'addresses': [{
    'city': 'a',
    'zipcode': 1,
    'current': False,
    'locations': [{
      'latitude': 1.5,
      'longitude': 3.8
    }, {
      'latitude': 2.9,
      'longitude': 15.3
    }],
  }, {
    'city': 'b',
    'zipcode': 2,
    'current': True,
    'locations': [{
      'latitude': 11.2,
      'longitude': 20.1
    }, {
      'latitude': 30.1,
      'longitude': 40.2
    }],
  }]
}


def test_field_infer_dtype() -> None:
  f = Field(repeated_field=Field(dtype=DataType.STRING))
  assert f.dtype == DataType.LIST

  f = Field(fields={'name': Field(dtype=DataType.STRING)})
  assert f.dtype == DataType.STRUCT


def test_field_ctor_validation() -> None:
  with pytest.raises(ValueError, match='"dtype" is required'):
    Field()

  with pytest.raises(ValueError, match='dtype needs to be STRUCT'):
    Field(dtype=DataType.STRING, fields={'name': Field(dtype=DataType.INT32)})

  with pytest.raises(ValueError, match='dtype needs to be LIST'):
    Field(dtype=DataType.STRING, repeated_field=Field(dtype=DataType.INT32))

  with pytest.raises(ValueError, match='Both "fields" and "repeated_field" should not be defined'):
    Field(
      fields={'name': Field(dtype=DataType.STRING)},
      repeated_field=Field(dtype=DataType.INT32),
    )


def test_schema_leafs() -> None:
  expected = {
    ('addresses', PATH_WILDCARD, 'city'): Field(dtype=DataType.STRING),
    ('addresses', PATH_WILDCARD, 'current'): Field(dtype=DataType.BOOLEAN),
    ('addresses', PATH_WILDCARD, 'locations', PATH_WILDCARD, 'latitude'):
      Field(dtype=DataType.FLOAT16),
    ('addresses', PATH_WILDCARD, 'locations', PATH_WILDCARD, 'longitude'):
      Field(dtype=DataType.FLOAT64),
    ('addresses', PATH_WILDCARD, 'zipcode'): Field(dtype=DataType.INT16),
    ('blob',): Field(dtype=DataType.BINARY),
    ('person', 'name'): Field(dtype=DataType.STRING),
    ('person', 'last_name'): Field(dtype=DataType.STRING_SPAN, derived_from=('person', 'name')),
    ('person', 'data', PATH_WILDCARD, PATH_WILDCARD): Field(dtype=DataType.FLOAT32)
  }
  assert NESTED_TEST_SCHEMA.leafs == expected


def test_schema_to_arrow_schema() -> None:
  expected = pa.schema({
    'person': pa.struct({
      'name': pa.string(),
      # The dtype for STRING_SPAN is implmemented as a struct with a {start, end}.
      'last_name': pa.struct({
        'start': pa.int32(),
        'end': pa.int32(),
      }),
      'data': pa.list_(pa.list_(pa.float32()))
    }),
    'addresses': pa.list_(
      pa.struct({
        'city': pa.string(),
        'zipcode': pa.int16(),
        'current': pa.bool_(),
        'locations': pa.list_(pa.struct({
          'latitude': pa.float16(),
          'longitude': pa.float64()
        })),
      })),
    'blob': pa.binary(),
  })
  arrow_schema = schema_to_arrow_schema(NESTED_TEST_SCHEMA)
  assert arrow_schema == expected


def test_arrow_schema_to_schema() -> None:
  arrow_schema = pa.schema({
    'person': pa.struct({
      'name': pa.string(),
      'data': pa.list_(pa.list_(pa.float32()))
    }),
    'addresses': pa.list_(
      pa.struct({
        'city': pa.string(),
        'zipcode': pa.int16(),
        'current': pa.bool_(),
        'locations': pa.list_(pa.struct({
          'latitude': pa.float16(),
          'longitude': pa.float64()
        })),
      })),
    'blob': pa.binary(),
  })
  expected = Schema(
    fields={
      'person': Field(
        fields={
          'name': Field(dtype=DataType.STRING),
          'data': Field(repeated_field=Field(repeated_field=Field(dtype=DataType.FLOAT32)))
        }),
      'addresses': Field(
        repeated_field=Field(
          fields={
            'city': Field(dtype=DataType.STRING),
            'zipcode': Field(dtype=DataType.INT16),
            'current': Field(dtype=DataType.BOOLEAN),
            'locations': Field(
              repeated_field=Field(
                fields={
                  'latitude': Field(dtype=DataType.FLOAT16),
                  'longitude': Field(dtype=DataType.FLOAT64),
                }))
          })),
      'blob': Field(dtype=DataType.BINARY),
    })
  schema = arrow_schema_to_schema(arrow_schema)
  assert schema == expected


def test_simple_schema_str() -> None:
  schema = Schema(fields={'person': Field(dtype=DataType.STRING)})
  assert str(schema) == 'person: string'


def test_child_item_from_column_path() -> None:
  assert child_item_from_column_path(NESTED_TEST_ITEM,
                                     ('addresses', 0, 'locations', 0, 'longitude')) == 3.8
  assert child_item_from_column_path(NESTED_TEST_ITEM, ('addresses', 1, 'city')) == 'b'


def test_child_item_from_column_path_raises_wildcard() -> None:
  with pytest.raises(
      ValueError, match='cannot be called with a path that contains a repeated wildcard'):
    child_item_from_column_path(NESTED_TEST_ITEM, ('addresses', PATH_WILDCARD, 'city'))


def test_column_paths_match() -> None:
  assert column_paths_match(path_match=('person', 'name'), specific_path=('person', 'name')) is True
  assert column_paths_match(
    path_match=('person', 'name'), specific_path=('person', 'not_name')) is False

  # Wildcards work for structs.
  assert column_paths_match(
    path_match=(PATH_WILDCARD, 'name'), specific_path=('person', 'name')) is True
  assert column_paths_match(
    path_match=(PATH_WILDCARD, 'name'), specific_path=('person', 'not_name')) is False

  # Wildcards work for repeateds.
  assert column_paths_match(
    path_match=('person', PATH_WILDCARD, 'name'), specific_path=('person', 0, 'name')) is True
  assert column_paths_match(
    path_match=('person', PATH_WILDCARD, 'name'), specific_path=('person', 0, 'not_name')) is False

  # Sub-path matches always return False.
  assert column_paths_match(path_match=(PATH_WILDCARD,), specific_path=('person', 'name')) is False
  assert column_paths_match(
    path_match=(
      'person',
      PATH_WILDCARD,
    ), specific_path=('person', 0, 'name')) is False


def test_nested_schema_str() -> None:

  assert str(NESTED_TEST_SCHEMA) == """\
person:
  name: string
  last_name: string_span
  data: list( list( float32))
addresses: list(
  city: string
  zipcode: int16
  current: boolean
  locations: list(
    latitude: float16
    longitude: float64))
blob: binary\
"""
