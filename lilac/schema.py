"""Item: an individual entry in the dataset."""

import csv
import io
from collections import deque
from datetime import datetime
from enum import Enum
from typing import Any, Optional, Union, cast

import numpy as np
import pyarrow as pa
from pydantic import BaseModel, StrictInt, StrictStr, validator
from typing_extensions import TypedDict

MANIFEST_FILENAME = 'manifest.json'
PARQUET_FILENAME_PREFIX = 'data'

# We choose `__rowid__` inspired by the standard `rowid` pseudocolumn in DBs:
# https://docs.oracle.com/cd/B19306_01/server.102/b14200/pseudocolumns008.htm
ROWID = '__rowid__'
PATH_WILDCARD = '*'
VALUE_KEY = '__value__'
SIGNAL_METADATA_KEY = '__metadata__'
TEXT_SPAN_START_FEATURE = 'start'
TEXT_SPAN_END_FEATURE = 'end'

EMBEDDING_KEY = 'embedding'

# Python doesn't work with recursive types. These types provide some notion of type-safety.
Scalar = Union[bool, datetime, int, float, str, bytes]
Item = Any

# Contains a string field name, a wildcard for repeateds, or a specific integer index for repeateds.
# This path represents a path to a particular column.
# Examples:
#  ['article', 'field'] represents {'article': {'field': VALUES}}
#  ['article', '*', 'field'] represents {'article': [{'field': VALUES}, {'field': VALUES}]}
#  ['article', '0', 'field'] represents {'article': {'field': VALUES}}
PathTuple = tuple[StrictStr, ...]
Path = Union[PathTuple, StrictStr]

PathKeyedItem = tuple[Path, Item]

# These fields are for for python only and not written to a schema.
RichData = Union[str, bytes]
VectorKey = tuple[Union[StrictStr, StrictInt], ...]
PathKey = VectorKey


class DataType(str, Enum):
  """Enum holding the dtype for a field."""
  STRING = 'string'
  # Contains {start, end} offset integers with a reference_column.
  STRING_SPAN = 'string_span'
  BOOLEAN = 'boolean'

  # Ints.
  INT8 = 'int8'
  INT16 = 'int16'
  INT32 = 'int32'
  INT64 = 'int64'
  UINT8 = 'uint8'
  UINT16 = 'uint16'
  UINT32 = 'uint32'
  UINT64 = 'uint64'

  # Floats.
  FLOAT16 = 'float16'
  FLOAT32 = 'float32'
  FLOAT64 = 'float64'

  ### Time ###
  # Time of day (no time zone).
  TIME = 'time'
  # Calendar date (year, month, day), no time zone.
  DATE = 'date'
  # An "Instant" stored as number of microseconds (µs) since 1970-01-01 00:00:00+00 (UTC time zone).
  TIMESTAMP = 'timestamp'
  # Time span, stored as microseconds.
  INTERVAL = 'interval'

  BINARY = 'binary'

  EMBEDDING = 'embedding'

  NULL = 'null'

  def __repr__(self) -> str:
    return self.value


class SignalInputType(str, Enum):
  """Enum holding the signal input type."""
  TEXT = 'text'
  TEXT_EMBEDDING = 'text_embedding'
  IMAGE = 'image'

  def __repr__(self) -> str:
    return self.value


SIGNAL_TYPE_TO_VALID_DTYPES: dict[SignalInputType, list[DataType]] = {
  SignalInputType.TEXT: [DataType.STRING, DataType.STRING_SPAN],
  SignalInputType.IMAGE: [DataType.BINARY],
}


def signal_type_supports_dtype(input_type: SignalInputType, dtype: DataType) -> bool:
  """Returns True if the signal compute type supports the dtype."""
  return dtype in SIGNAL_TYPE_TO_VALID_DTYPES[input_type]


Bin = tuple[str, Optional[Union[float, int]], Optional[Union[float, int]]]


class Field(BaseModel):
  """Holds information for a field in the schema."""
  repeated_field: Optional['Field'] = None
  fields: Optional[dict[str, 'Field']] = None
  dtype: Optional[DataType] = None
  # Defined as the serialized signal when this field is the root result of a signal.
  signal: Optional[dict[str, Any]] = None
  # Maps a named bin to a tuple of (start, end) values.
  bins: Optional[list[Bin]] = None
  categorical: Optional[bool] = None

  @validator('fields')
  def either_fields_or_repeated_field_is_defined(
      cls, fields: Optional[dict[str, 'Field']], values: dict[str,
                                                              Any]) -> Optional[dict[str, 'Field']]:
    """Error if both `fields` and `repeated_fields` are defined."""
    if not fields:
      return fields
    if values.get('repeated_field'):
      raise ValueError('Both "fields" and "repeated_field" should not be defined')
    if VALUE_KEY in fields:
      raise ValueError(f'{VALUE_KEY} is a reserved field name.')
    return fields

  @validator('dtype', always=True)
  def infer_default_dtype(cls, dtype: Optional[DataType], values: dict[str,
                                                                       Any]) -> Optional[DataType]:
    """Infers the default value for dtype if not explicitly provided."""
    if dtype and values.get('repeated_field'):
      raise ValueError('dtype and repeated_field cannot both be defined.')
    if not values.get('repeated_field') and not values.get('fields') and not dtype:
      raise ValueError('One of "fields", "repeated_field", or "dtype" should be defined')
    return dtype

  @validator('bins')
  def validate_bins(cls, bins: list[Bin]) -> list[Bin]:
    """Validate the bins."""
    if len(bins) < 2:
      raise ValueError('Please specify at least two bins.')
    _, first_start, _ = bins[0]
    if first_start is not None:
      raise ValueError('The first bin should have a `None` start value.')
    _, _, last_end = bins[-1]
    if last_end is not None:
      raise ValueError('The last bin should have a `None` end value.')
    for i, (_, start, _) in enumerate(bins):
      if i == 0:
        continue
      prev_bin = bins[i - 1]
      _, _, prev_end = prev_bin
      if start != prev_end:
        raise ValueError(
          f'Bin {i} start ({start}) should be equal to the previous bin end {prev_end}.')
    return bins

  @validator('categorical')
  def validate_categorical(cls, categorical: bool, values: dict[str, Any]) -> bool:
    """Validate the categorical field."""
    if categorical and is_float(values['dtype']):
      raise ValueError('Categorical fields cannot be float dtypes.')
    return categorical

  def __str__(self) -> str:
    return _str_field(self, indent=0)

  def __repr__(self) -> str:
    return f' {self.__class__.__name__}::{self.json(exclude_none=True, indent=2)}'


class Schema(BaseModel):
  """Database schema."""
  fields: dict[str, Field]
  # Cached leafs.
  _leafs: Optional[dict[PathTuple, Field]] = None
  # Cached flat list of all the fields.
  _all_fields: Optional[list[tuple[PathTuple, Field]]] = None

  class Config:
    arbitrary_types_allowed = True
    underscore_attrs_are_private = True

  @property
  def leafs(self) -> dict[PathTuple, Field]:
    """Return all the leaf fields in the schema. A leaf is defined as a node that contains a value.

    NOTE: Leafs may contain children. Leafs can be found as any node that has a dtype defined.
    """
    if self._leafs:
      return self._leafs
    result: dict[PathTuple, Field] = {}
    q: deque[tuple[PathTuple, Field]] = deque([((), Field(fields=self.fields))])
    while q:
      path, field = q.popleft()
      if field.dtype:
        # Nodes with dtypes act as leafs. They also may have children.
        result[path] = field
      if field.fields:
        for name, child_field in field.fields.items():
          child_path = (*path, name)
          q.append((child_path, child_field))
      elif field.repeated_field:
        child_path = (*path, PATH_WILDCARD)
        q.append((child_path, field.repeated_field))

    self._leafs = result
    return result

  @property
  def all_fields(self) -> list[tuple[PathTuple, Field]]:
    """Return all the fields in the schema as a flat list."""
    if self._all_fields:
      return self._all_fields
    result: list[tuple[PathTuple, Field]] = []
    q: deque[tuple[PathTuple, Field]] = deque([((), Field(fields=self.fields))])
    while q:
      path, field = q.popleft()
      if path:
        result.append((path, field))
      if field.fields:
        for name, child_field in field.fields.items():
          child_path = (*path, name)
          q.append((child_path, child_field))
      elif field.repeated_field:
        child_path = (*path, PATH_WILDCARD)
        q.append((child_path, field.repeated_field))

    self._all_fields = result
    return result

  def has_field(self, path: PathTuple) -> bool:
    """Returns if the field is found at the given path."""
    field = cast(Field, self)
    for path_part in path:
      if field.fields:
        field = cast(Field, field.fields.get(path_part))
        if not field:
          return False
      elif field.repeated_field:
        if path_part != PATH_WILDCARD:
          return False
        field = field.repeated_field
      else:
        return False
    return True

  def get_field(self, path: PathTuple) -> Field:
    """Returns the field at the given path."""
    if path == (ROWID,):
      return Field(dtype=DataType.STRING)
    field = cast(Field, self)
    for name in path:
      if field.fields:
        if name not in field.fields:
          raise ValueError(f'Path {path} not found in schema')
        field = field.fields[name]
      elif field.repeated_field:
        if name != PATH_WILDCARD:
          raise ValueError(f'Invalid path {path}')
        field = field.repeated_field
      else:
        raise ValueError(f'Invalid path {path}')
    return field

  def __str__(self) -> str:
    return _str_fields(self.fields, indent=0)

  def __repr__(self) -> str:
    return self.json(exclude_none=True, indent=2)


def schema(schema_like: object) -> Schema:
  """Parse a schema-like object to a Schema object."""
  field = _parse_field_like(schema_like)
  if not field.fields:
    raise ValueError('Schema must have fields')
  return Schema(fields=field.fields)


def field(
  dtype: Optional[Union[DataType, str]] = None,
  signal: Optional[dict] = None,
  fields: Optional[object] = None,
  bins: Optional[list[Bin]] = None,
  categorical: Optional[bool] = None,
) -> Field:
  """Parse a field-like object to a Field object."""
  field = _parse_field_like(fields or {}, dtype)
  if signal:
    field.signal = signal
  if dtype:
    if isinstance(dtype, str):
      dtype = DataType(dtype)
    field.dtype = dtype
  if bins:
    field.bins = bins
  if categorical is not None:
    field.categorical = categorical
  return field


class SpanVector(TypedDict):
  """A span with a vector."""
  span: tuple[int, int]
  vector: np.ndarray


def lilac_span(start: int, end: int, metadata: dict[str, Any] = {}) -> Item:
  """Creates a lilac span item, representing a pointer to a slice of text."""
  return {VALUE_KEY: {TEXT_SPAN_START_FEATURE: start, TEXT_SPAN_END_FEATURE: end}, **metadata}


def lilac_embedding(start: int, end: int, embedding: Optional[np.ndarray]) -> Item:
  """Creates a lilac embedding item, representing a vector with a pointer to a slice of text."""
  return lilac_span(start, end, {EMBEDDING_KEY: embedding})


def _parse_field_like(field_like: object, dtype: Optional[Union[DataType, str]] = None) -> Field:
  if isinstance(field_like, Field):
    return field_like
  elif isinstance(field_like, dict):
    fields: dict[str, Field] = {}
    for k, v in field_like.items():
      fields[k] = _parse_field_like(v)
    if isinstance(dtype, str):
      dtype = DataType(dtype)
    return Field(fields=fields or None, dtype=dtype)
  elif isinstance(field_like, str):
    return Field(dtype=DataType(field_like))
  elif isinstance(field_like, list):
    return Field(repeated_field=_parse_field_like(field_like[0], dtype=dtype))
  else:
    raise ValueError(f'Cannot parse field like: {field_like}')


def child_item_from_column_path(item: Item, path: Path) -> Item:
  """Return the last (child) item from a column path."""
  child_item_value = item
  for path_part in path:
    if path_part == PATH_WILDCARD:
      raise ValueError(
        'child_item_from_column_path cannot be called with a path that contains a repeated '
        f'wildcard: "{path}"')
    # path_part can either be an integer or a string for a dictionary, both of which we can
    # directly index with.
    child_path = int(path_part) if path_part.isdigit() else path_part
    child_item_value = child_item_value[child_path]
  return child_item_value


def column_paths_match(path_match: Path, specific_path: Path) -> bool:
  """Test whether two column paths match.

  Args:
    path_match: A column path that contains wildcards, and sub-paths. This path will be used for
       testing the second specific path.
    specific_path: A column path that specifically identifies an field.

  Returns
    Whether specific_path matches the path_match. This will only match when the
    paths are equal length. If a user wants to enrich everything with an array, they must use the
    path wildcard '*' in their patch match.
  """
  if isinstance(path_match, str):
    path_match = (path_match,)
  if isinstance(specific_path, str):
    specific_path = (specific_path,)

  if len(path_match) != len(specific_path):
    return False

  for path_match_p, specific_path_p in zip(path_match, specific_path):
    if path_match_p == PATH_WILDCARD:
      continue

    if path_match_p != specific_path_p:
      return False

  return True


def normalize_path(path: Path) -> PathTuple:
  """Normalizes a dot seperated path, but ignores dots inside quotes, like regular SQL.

  Examples
  - 'a.b.c' will be parsed as ('a', 'b', 'c').
  - '"a.b".c' will be parsed as ('a.b', 'c').
  - '"a".b.c' will be parsed as ('a', 'b', 'c').
  """
  if isinstance(path, str):
    return tuple(next(csv.reader(io.StringIO(path), delimiter='.')))
  return path


class ImageInfo(BaseModel):
  """Info about an individual image."""
  path: Path


class SourceManifest(BaseModel):
  """The manifest that describes the dataset run, including schema and parquet files."""
  # List of a parquet filepaths storing the data. The paths can be relative to `manifest.json`.
  files: list[str]
  # The data schema.
  data_schema: Schema

  # Image information for the dataset.
  images: Optional[list[ImageInfo]] = None


def _str_fields(fields: dict[str, Field], indent: int) -> str:
  prefix = ' ' * indent
  out: list[str] = []
  for name, field in fields.items():
    out.append(f'{prefix}{name}:{_str_field(field, indent=indent + 2)}')
  return '\n'.join(out)


def _str_field(field: Field, indent: int) -> str:
  if field.fields:
    prefix = '\n' if indent > 0 else ''
    return f'{prefix}{_str_fields(field.fields, indent)}'
  if field.repeated_field:
    return f' list({_str_field(field.repeated_field, indent)})'
  return f' {cast(DataType, field.dtype)}'


def dtype_to_arrow_schema(dtype: DataType) -> Union[pa.Schema, pa.DataType]:
  """Convert the dtype to an arrow dtype."""
  if dtype == DataType.STRING:
    return pa.string()
  elif dtype == DataType.BOOLEAN:
    return pa.bool_()
  elif dtype == DataType.FLOAT16:
    return pa.float16()
  elif dtype == DataType.FLOAT32:
    return pa.float32()
  elif dtype == DataType.FLOAT64:
    return pa.float64()
  elif dtype == DataType.INT8:
    return pa.int8()
  elif dtype == DataType.INT16:
    return pa.int16()
  elif dtype == DataType.INT32:
    return pa.int32()
  elif dtype == DataType.INT64:
    return pa.int64()
  elif dtype == DataType.UINT8:
    return pa.uint8()
  elif dtype == DataType.UINT16:
    return pa.uint16()
  elif dtype == DataType.UINT32:
    return pa.uint32()
  elif dtype == DataType.UINT64:
    return pa.uint64()
  elif dtype == DataType.BINARY:
    return pa.binary()
  elif dtype == DataType.TIME:
    return pa.time64()
  elif dtype == DataType.DATE:
    return pa.date64()
  elif dtype == DataType.TIMESTAMP:
    return pa.timestamp('us')
  elif dtype == DataType.INTERVAL:
    return pa.duration('us')
  elif dtype == DataType.EMBEDDING:
    # We reserve an empty column for embeddings in parquet files so they can be queried.
    # The values are *not* filled out. If parquet and duckdb support embeddings in the future, we
    # can set this dtype to the relevant pyarrow type.
    return pa.null()
  elif dtype == DataType.STRING_SPAN:
    return pa.struct({
      VALUE_KEY: pa.struct({
        TEXT_SPAN_START_FEATURE: pa.int32(),
        TEXT_SPAN_END_FEATURE: pa.int32()
      })
    })
  elif dtype == DataType.NULL:
    return pa.null()
  else:
    raise ValueError(f'Can not convert dtype "{dtype}" to arrow dtype')


def schema_to_arrow_schema(schema: Union[Schema, Field]) -> pa.Schema:
  """Convert our schema to arrow schema."""
  arrow_schema = cast(pa.Schema, _schema_to_arrow_schema_impl(schema))
  arrow_fields = {field.name: field.type for field in arrow_schema}
  return pa.schema(arrow_fields)


def _schema_to_arrow_schema_impl(schema: Union[Schema, Field]) -> Union[pa.Schema, pa.DataType]:
  """Convert a schema to an apache arrow schema."""
  if schema.fields:
    arrow_fields: dict[str, Union[pa.Schema, pa.DataType]] = {}
    for name, field in schema.fields.items():
      if name == ROWID:
        arrow_schema = dtype_to_arrow_schema(cast(DataType, field.dtype))
      else:
        arrow_schema = _schema_to_arrow_schema_impl(field)
      arrow_fields[name] = arrow_schema

    if isinstance(schema, Schema):
      # Top-level schemas do not have __value__ fields.
      return pa.schema(arrow_fields)
    else:
      # When nodes have both dtype and children, we add __value__ alongside the fields.
      if schema.dtype:
        value_schema = dtype_to_arrow_schema(schema.dtype)
        if schema.dtype == DataType.STRING_SPAN:
          value_schema = value_schema[VALUE_KEY].type
        arrow_fields[VALUE_KEY] = value_schema

      return pa.struct(arrow_fields)

  field = cast(Field, schema)
  if field.repeated_field:
    return pa.list_(_schema_to_arrow_schema_impl(field.repeated_field))

  return dtype_to_arrow_schema(cast(DataType, field.dtype))


def arrow_dtype_to_dtype(arrow_dtype: pa.DataType) -> DataType:
  """Convert arrow dtype to our dtype."""
  # Ints.
  if arrow_dtype == pa.int8():
    return DataType.INT8
  elif arrow_dtype == pa.int16():
    return DataType.INT16
  elif arrow_dtype == pa.int32():
    return DataType.INT32
  elif arrow_dtype == pa.int64():
    return DataType.INT64
  elif arrow_dtype == pa.uint8():
    return DataType.UINT8
  elif arrow_dtype == pa.uint16():
    return DataType.UINT16
  elif arrow_dtype == pa.uint32():
    return DataType.UINT32
  elif arrow_dtype == pa.uint64():
    return DataType.UINT64
  # Floats.
  elif arrow_dtype == pa.float16():
    return DataType.FLOAT16
  elif arrow_dtype == pa.float32():
    return DataType.FLOAT32
  elif arrow_dtype == pa.float64():
    return DataType.FLOAT64
  # Time.
  elif pa.types.is_time(arrow_dtype):
    return DataType.TIME
  elif pa.types.is_date(arrow_dtype):
    return DataType.DATE
  elif pa.types.is_timestamp(arrow_dtype):
    return DataType.TIMESTAMP
  elif pa.types.is_duration(arrow_dtype):
    return DataType.INTERVAL
  # Others.
  elif arrow_dtype == pa.string():
    return DataType.STRING
  elif pa.types.is_binary(arrow_dtype) or pa.types.is_fixed_size_binary(arrow_dtype):
    return DataType.BINARY
  elif pa.types.is_boolean(arrow_dtype):
    return DataType.BOOLEAN
  elif arrow_dtype == pa.null():
    return DataType.NULL
  else:
    raise ValueError(f'Can not convert arrow dtype "{arrow_dtype}" to our dtype')


def arrow_schema_to_schema(schema: pa.Schema) -> Schema:
  """Convert arrow schema to our schema."""
  # TODO(nsthorat): Change this implementation to allow more complicated reading of arrow schemas
  # into our schema by inferring values when {__value__: value} is present in the pyarrow schema.
  # This isn't necessary today as this util is only needed by sources which do not have data in the
  # lilac format.
  return cast(Schema, _arrow_schema_to_schema_impl(schema))


def _arrow_schema_to_schema_impl(schema: Union[pa.Schema, pa.DataType]) -> Union[Schema, Field]:
  """Convert an apache arrow schema to our schema."""
  if isinstance(schema, (pa.Schema, pa.StructType)):
    fields: dict[str, Field] = {
      field.name: cast(Field, _arrow_schema_to_schema_impl(field.type)) for field in schema
    }
    return Schema(fields=fields) if isinstance(schema, pa.Schema) else Field(fields=fields)
  elif isinstance(schema, pa.ListType):
    return Field(repeated_field=cast(Field, _arrow_schema_to_schema_impl(schema.value_field.type)))
  else:
    return Field(dtype=arrow_dtype_to_dtype(schema))


def is_float(dtype: DataType) -> bool:
  """Check if a dtype is a float dtype."""
  return dtype in [DataType.FLOAT16, DataType.FLOAT32, DataType.FLOAT64]


def is_integer(dtype: DataType) -> bool:
  """Check if a dtype is an integer dtype."""
  return dtype in [
    DataType.INT8, DataType.INT16, DataType.INT32, DataType.INT64, DataType.UINT8, DataType.UINT16,
    DataType.UINT32, DataType.UINT64
  ]


def is_temporal(dtype: DataType) -> bool:
  """Check if a dtype is a temporal dtype."""
  return dtype in [DataType.TIME, DataType.DATE, DataType.TIMESTAMP, DataType.INTERVAL]


def is_ordinal(dtype: DataType) -> bool:
  """Check if a dtype is an ordinal dtype."""
  return is_float(dtype) or is_integer(dtype) or is_temporal(dtype)
