"""Tests for item.py."""

import pyarrow as pa
import pytest

from .schema import (
  BINARY,
  BOOLEAN,
  FLOAT16,
  FLOAT32,
  FLOAT64,
  INT16,
  INT32,
  PATH_WILDCARD,
  SPAN_KEY,
  STRING,
  STRING_SPAN,
  TEXT_SPAN_END_FEATURE,
  TEXT_SPAN_START_FEATURE,
  VALUE_KEY,
  Field,
  Item,
  arrow_schema_to_schema,
  column_paths_match,
  field,
  schema,
  schema_to_arrow_schema,
)

NESTED_TEST_SCHEMA = schema(
  {
    'person': {
      'name': 'string',
      'last_name': 'string_span',
      # Contains a double nested array of primitives.
      'data': [['float32']],
      # Contains a value and children.
      'description': field(
        'string',
        fields={
          'toxicity': 'float32',
          'sentences': [field('string_span', fields={'len': 'int32'})],
        },
      ),
    },
    'addresses': [
      {
        'city': 'string',
        'zipcode': 'int16',
        'current': 'boolean',
        'locations': [{'latitude': 'float16', 'longitude': 'float64'}],
      }
    ],
    'blob': 'binary',
  }
)
NESTED_TEST_ITEM: Item = {
  'person': {'name': 'Test Name', 'last_name': (5, 9)},
  'addresses': [
    {
      'city': 'a',
      'zipcode': 1,
      'current': False,
      'locations': [{'latitude': 1.5, 'longitude': 3.8}, {'latitude': 2.9, 'longitude': 15.3}],
    },
    {
      'city': 'b',
      'zipcode': 2,
      'current': True,
      'locations': [{'latitude': 11.2, 'longitude': 20.1}, {'latitude': 30.1, 'longitude': 40.2}],
    },
  ],
}


def test_field_ctor_validation() -> None:
  with pytest.raises(
    ValueError, match='One of "fields", "repeated_field", or "dtype" should be defined'
  ):
    Field()

  with pytest.raises(ValueError, match='Both "fields" and "repeated_field" should not be defined'):
    Field(fields={'name': Field(dtype=STRING)}, repeated_field=Field(dtype=INT32))

  with pytest.raises(ValueError, match=f'{VALUE_KEY} is a reserved field name'):
    Field(fields={VALUE_KEY: Field(dtype=STRING)})


def test_schema_leafs() -> None:
  expected = {
    ('addresses', PATH_WILDCARD, 'city'): Field(dtype=STRING),
    ('addresses', PATH_WILDCARD, 'current'): Field(dtype=BOOLEAN),
    ('addresses', PATH_WILDCARD, 'locations', PATH_WILDCARD, 'latitude'): Field(dtype=FLOAT16),
    ('addresses', PATH_WILDCARD, 'locations', PATH_WILDCARD, 'longitude'): Field(dtype=FLOAT64),
    ('addresses', PATH_WILDCARD, 'zipcode'): Field(dtype=INT16),
    ('blob',): Field(dtype=BINARY),
    ('person', 'name'): Field(dtype=STRING),
    ('person', 'last_name'): Field(dtype=STRING_SPAN),
    ('person', 'data', PATH_WILDCARD, PATH_WILDCARD): Field(dtype=FLOAT32),
    ('person', 'description'): Field(
      dtype=STRING,
      fields={
        'toxicity': Field(dtype=FLOAT32),
        'sentences': Field(
          repeated_field=Field(dtype=STRING_SPAN, fields={'len': Field(dtype=INT32)})
        ),
      },
    ),
    ('person', 'description', 'toxicity'): Field(dtype=FLOAT32),
    ('person', 'description', 'sentences', PATH_WILDCARD): Field(
      fields={'len': Field(dtype=INT32)}, dtype=STRING_SPAN
    ),
    ('person', 'description', 'sentences', PATH_WILDCARD, 'len'): Field(dtype=INT32),
  }
  assert NESTED_TEST_SCHEMA.leafs == expected


def test_schema_to_arrow_schema() -> None:
  arrow_schema = schema_to_arrow_schema(NESTED_TEST_SCHEMA)

  assert arrow_schema == pa.schema(
    {
      'person': pa.struct(
        {
          'name': pa.string(),
          # The dtype for STRING_SPAN is implemented as a struct with a {start, end}.
          'last_name': pa.struct(
            {
              SPAN_KEY: pa.struct(
                {TEXT_SPAN_START_FEATURE: pa.int32(), TEXT_SPAN_END_FEATURE: pa.int32()}
              )
            }
          ),
          'data': pa.list_(pa.list_(pa.float32())),
          'description': pa.struct(
            {
              'toxicity': pa.float32(),
              'sentences': pa.list_(
                pa.struct(
                  {
                    'len': pa.int32(),
                    SPAN_KEY: pa.struct(
                      {TEXT_SPAN_START_FEATURE: pa.int32(), TEXT_SPAN_END_FEATURE: pa.int32()}
                    ),
                  }
                )
              ),
              VALUE_KEY: pa.string(),
            }
          ),
        }
      ),
      'addresses': pa.list_(
        pa.struct(
          {
            'city': pa.string(),
            'zipcode': pa.int16(),
            'current': pa.bool_(),
            'locations': pa.list_(pa.struct({'latitude': pa.float16(), 'longitude': pa.float64()})),
          }
        )
      ),
      'blob': pa.binary(),
    }
  )


def test_arrow_schema_to_schema() -> None:
  arrow_schema = pa.schema(
    {
      'person': pa.struct({'name': pa.string(), 'data': pa.list_(pa.list_(pa.float32()))}),
      'addresses': pa.list_(
        pa.struct(
          {
            'city': pa.string(),
            'zipcode': pa.int16(),
            'current': pa.bool_(),
            'locations': pa.list_(pa.struct({'latitude': pa.float16(), 'longitude': pa.float64()})),
          }
        )
      ),
      'blob': pa.binary(),
      'spans': pa.struct(
        {SPAN_KEY: pa.struct({'start': pa.int32(), 'end': pa.int32()}), 'metadata': pa.string()}
      ),
    }
  )
  expected_schema = schema(
    {
      'person': {'name': 'string', 'data': [['float32']]},
      'addresses': [
        {
          'city': 'string',
          'zipcode': 'int16',
          'current': 'boolean',
          'locations': [{'latitude': 'float16', 'longitude': 'float64'}],
        }
      ],
      'blob': 'binary',
      'spans': field('string_span', fields={'metadata': 'string'}),
    }
  )
  assert arrow_schema_to_schema(arrow_schema) == expected_schema


def test_simple_schema_str() -> None:
  assert str(schema({'person': 'string'})) == 'person: string'


def test_column_paths_match() -> None:
  assert column_paths_match(path_match=('person', 'name'), specific_path=('person', 'name')) is True
  assert (
    column_paths_match(path_match=('person', 'name'), specific_path=('person', 'not_name')) is False
  )

  # Wildcards work for structs.
  assert (
    column_paths_match(path_match=(PATH_WILDCARD, 'name'), specific_path=('person', 'name')) is True
  )
  assert (
    column_paths_match(path_match=(PATH_WILDCARD, 'name'), specific_path=('person', 'not_name'))
    is False
  )

  # Wildcards work for repeateds.
  assert (
    column_paths_match(
      path_match=('person', PATH_WILDCARD, 'name'), specific_path=('person', '0', 'name')
    )
    is True
  )
  assert (
    column_paths_match(
      path_match=('person', PATH_WILDCARD, 'name'), specific_path=('person', '0', 'not_name')
    )
    is False
  )

  # Sub-path matches always return False.
  assert column_paths_match(path_match=(PATH_WILDCARD,), specific_path=('person', 'name')) is False
  assert (
    column_paths_match(path_match=('person', PATH_WILDCARD), specific_path=('person', '0', 'name'))
    is False
  )


def test_nested_schema_str() -> None:
  assert (
    str(NESTED_TEST_SCHEMA)
    == """\
person:
  name: string
  last_name: string_span
  data: list( list( float32))
  description:
    toxicity: float32
    sentences: list(
      len: int32)
addresses: list(
  city: string
  zipcode: int16
  current: boolean
  locations: list(
    latitude: float16
    longitude: float64))
blob: binary\
"""
  )
