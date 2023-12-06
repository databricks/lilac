"""Schema utils for interfacing with the duckdb database."""

from typing import Optional, cast

from .schema import (
  BINARY,
  BOOLEAN,
  DATE,
  EMBEDDING,
  FLOAT16,
  FLOAT32,
  FLOAT64,
  INT8,
  INT16,
  INT32,
  INT64,
  INTERVAL,
  NULL,
  ROWID,
  SPAN_KEY,
  STRING,
  STRING_SPAN,
  TEXT_SPAN_END_FEATURE,
  TEXT_SPAN_START_FEATURE,
  TIME,
  TIMESTAMP,
  UINT8,
  UINT16,
  UINT32,
  UINT64,
  VALUE_KEY,
  DataType,
  Field,
  MapType,
  Schema,
)


def escape_string_literal(string: str) -> str:
  """Escape a string literal for duckdb."""
  string = string.replace("'", "''")
  return f"'{string}'"


def escape_col_name(col_name: str) -> str:
  """Escape a column name for duckdb."""
  col_name = col_name.replace('"', '""')
  return f'"{col_name}"'


def _duckdb_type(dtype: Optional[DataType]) -> str:
  """Convert the dtype to a duckdb type."""
  if dtype == STRING:
    return 'VARCHAR'
  elif dtype == BOOLEAN:
    return 'BOOLEAN'
  elif dtype == FLOAT16:
    return 'FLOAT'
  elif dtype == FLOAT32:
    return 'FLOAT'
  elif dtype == FLOAT64:
    return 'DOUBLE'
  elif dtype == INT8:
    return 'TINYINT'
  elif dtype == INT16:
    return 'SMALLINT'
  elif dtype == INT32:
    return 'INTEGER'
  elif dtype == INT64:
    return 'BIGINT'
  elif dtype == UINT8:
    return 'UTINYINT'
  elif dtype == UINT16:
    return 'USMALLINT'
  elif dtype == UINT32:
    return 'UINTEGER'
  elif dtype == UINT64:
    return 'UBIGINT'
  elif dtype == BINARY:
    return 'BLOB'
  elif dtype == TIME:
    return 'TIME'
  elif dtype == DATE:
    return 'DATE'
  elif dtype == TIMESTAMP:
    return 'TIMESTAMP'
  elif dtype == INTERVAL:
    return 'INTERVAL'
  elif dtype == EMBEDDING:
    # We reserve an empty column for embeddings in parquet files so they can be queried.
    # The values are *not* filled out. If parquet and duckdb support embeddings in the future, we
    # can set this dtype to the relevant type.
    return 'NULL'
  elif dtype == STRING_SPAN:
    return (
      f'STRUCT("{SPAN_KEY}" STRUCT("{TEXT_SPAN_START_FEATURE}" INT, "{TEXT_SPAN_END_FEATURE}" INT))'
    )
  elif dtype == NULL:
    return 'NULL'
  elif dtype is None:
    return 'NULL'
  elif dtype.type == 'map':
    map_dtype = cast(MapType, dtype)
    return f'MAP({_duckdb_type(map_dtype.key_type)}, {_duckdb_struct(map_dtype.value_field)})'
  else:
    raise ValueError(f'Can not convert dtype "{dtype}" to duckdb type')


def _duckdb_struct(field: Field) -> str:
  """Convert a field to a duckdb struct."""
  if field.fields:
    fields: dict[str, str] = {}
    for name, subfield in field.fields.items():
      fields[name] = _duckdb_type(subfield.dtype) if name == ROWID else _duckdb_struct(subfield)

    # When nodes have both dtype and children, we add __value__ alongside the fields.
    if field.dtype:
      if field.dtype == STRING_SPAN:
        fields[SPAN_KEY] = f'STRUCT("{TEXT_SPAN_START_FEATURE}" INT, "{TEXT_SPAN_END_FEATURE}" INT)'
      else:
        fields[VALUE_KEY] = _duckdb_type(field.dtype)

    members = [f'{escape_col_name(name)} {dtype}' for name, dtype in fields.items()]
    return f'STRUCT({", ".join(members)})'

  if field.repeated_field:
    return f'{_duckdb_struct(field.repeated_field)}[]'

  return _duckdb_type(field.dtype)


def duckdb_schema(schema: Schema) -> str:
  """Convert our schema to duckdb schema."""
  members: list[str] = [
    f'{escape_string_literal(name)}: {escape_string_literal(_duckdb_struct(field))}'
    for name, field in schema.fields.items()
  ]
  return '{' + ', '.join(members) + '}'
