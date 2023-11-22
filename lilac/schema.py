"""Item: an individual entry in the dataset."""

import csv
import io
from collections import deque
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Literal, Optional, Protocol, Sequence, Union, cast

import numpy as np
import pyarrow as pa
from pydantic import (
  BaseModel,
  ConfigDict,
  StrictInt,
  StrictStr,
  ValidationInfo,
  field_validator,
  model_validator,
)
from pydantic.functional_validators import ModelWrapValidatorHandler
from typing_extensions import TypedDict

from .utils import is_primitive, log

MANIFEST_FILENAME = 'manifest.json'
PARQUET_FILENAME_PREFIX = 'data'

# We choose `__rowid__` inspired by the standard `rowid` pseudocolumn in DBs:
# https://docs.oracle.com/cd/B19306_01/server.102/b14200/pseudocolumns008.htm
ROWID = '__rowid__'
PATH_WILDCARD = '*'
SPAN_KEY = '__span__'
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
PathTuple = tuple[str, ...]
Path = Union[PathTuple, str]

PathKeyedItem = tuple[Path, Item]

# These fields are for for python only and not written to a schema.
RichData = Union[str, bytes]
VectorKey = tuple[Union[StrictStr, StrictInt], ...]
PathKey = VectorKey


class DataType(BaseModel):
  """The data type for a field."""

  type: Literal[
    'string',
    'string_span',
    'boolean',
    'int8',
    'int16',
    'int32',
    'int64',
    'uint8',
    'uint16',
    'uint32',
    'uint64',
    'float16',
    'float32',
    'float64',
    'time',
    'date',
    'timestamp',
    'interval',
    'binary',
    'embedding',
    'null',
    'map',
  ]

  def __init__(self, type: str, **kwargs: Any) -> None:
    super().__init__(type=type, **kwargs)

  @model_validator(mode='wrap')  # type: ignore
  def convert_str_to_dtype(v: Any, handler: ModelWrapValidatorHandler['DataType']) -> 'DataType':
    """Convert a string to a DataType."""
    if isinstance(v, str):
      v = {'type': v}
    return handler(v)

  def __str__(self) -> str:
    return self.type

  def __repr__(self) -> str:
    return self.type


def change_const_to_enum(prop_name: str, value: str) -> Callable[[dict[str, Any]], None]:
  """Replace the const value in the schema to an enum with 1 value so typescript codegen works."""

  def _schema_extra(schema: dict[str, Any]) -> None:
    schema['properties'][prop_name] = {'enum': [value]}
    if 'required' not in schema:
      schema['required'] = []
    schema['required'].append(prop_name)

  return _schema_extra


class MapType(DataType):
  """The map dtype parameterized by the key and value types."""

  def __init__(self, **kwargs: Any) -> None:
    kwargs.pop('type', None)
    super().__init__(type='map', **kwargs)

  type: Literal['map'] = 'map'
  key_type: DataType
  value_type: DataType

  model_config = ConfigDict(json_schema_extra=change_const_to_enum('type', 'map'))

  def __str__(self) -> str:
    return f'map<{self.key_type}, {self.value_type}>'


STRING = DataType('string')
# Contains {start, end} offset integers with a reference_column.
STRING_SPAN = DataType('string_span')
BOOLEAN = DataType('boolean')

# Ints.
INT8 = DataType('int8')
INT16 = DataType('int16')
INT32 = DataType('int32')
INT64 = DataType('int64')
UINT8 = DataType('uint8')
UINT16 = DataType('uint16')
UINT32 = DataType('uint32')
UINT64 = DataType('uint64')

# Floats.
FLOAT16 = DataType('float16')
FLOAT32 = DataType('float32')
FLOAT64 = DataType('float64')

### Time ###
# Time of day (no time zone).
TIME = DataType('time')
# Calendar date (year, month, day), no time zone.
DATE = DataType('date')
# An "Instant" stored as number of microseconds (µs) since 1970-01-01 00:00:00+00 (UTC time zone).
TIMESTAMP = DataType('timestamp')
# Time span, stored as microseconds.
INTERVAL = DataType('interval')

BINARY = DataType('binary')

EMBEDDING = DataType('embedding')

NULL = DataType('null')


class SignalInputType(str, Enum):
  """Enum holding the signal input type."""

  TEXT = 'text'
  TEXT_EMBEDDING = 'text_embedding'
  IMAGE = 'image'
  ANY = 'any'

  def __repr__(self) -> str:
    return self.value


EmbeddingInputType = Literal['question', 'document']


SIGNAL_TYPE_TO_VALID_DTYPES: dict[SignalInputType, list[DataType]] = {
  SignalInputType.TEXT: [STRING, STRING_SPAN],
  SignalInputType.IMAGE: [BINARY],
}


def signal_type_supports_dtype(input_type: SignalInputType, dtype: DataType) -> bool:
  """Returns True if the signal compute type supports the dtype."""
  if input_type == SignalInputType.ANY:
    return True
  return dtype in SIGNAL_TYPE_TO_VALID_DTYPES[input_type]


Bin = tuple[str, Optional[Union[float, int]], Optional[Union[float, int]]]


class MapFn(Protocol):
  """Interface for a map function."""

  __name__: str

  def __call__(self, row: Item, job_id: int) -> Item:
    """Calls the map function, mapping an item to an item.

    Argumnets:
      row: An Item, a dictionary of an entire row.
      job_id: The job id.
    """
    ...


class MapInfo(BaseModel):
  """Holds information about a map that was run on a dataset."""

  fn_name: str
  fn_source: str
  date_created: datetime


class Field(BaseModel):
  """Holds information for a field in the schema."""

  repeated_field: Optional['Field'] = None
  fields: Optional[dict[str, 'Field']] = None
  dtype: Optional[Union[MapType, DataType]] = None
  # Defined as the serialized signal when this field is the root result of a signal.
  signal: Optional[dict[str, Any]] = None
  # Defined as the label name when the field is a label.
  label: Optional[str] = None
  # Defined when the field is generated by a map.
  map: Optional[MapInfo] = None
  # Maps a named bin to a tuple of (start, end) values.
  bins: Optional[list[Bin]] = None
  categorical: Optional[bool] = None

  @field_validator('fields')
  @classmethod
  def validate_fields(cls, fields: Optional[dict[str, 'Field']]) -> Optional[dict[str, 'Field']]:
    """Validate the fields."""
    if not fields:
      return fields
    if VALUE_KEY in fields:
      raise ValueError(f'{VALUE_KEY} is a reserved field name.')
    return fields

  @field_validator('bins')
  @classmethod
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
          f'Bin {i} start ({start}) should be equal to the previous bin end {prev_end}.'
        )
    return bins

  @field_validator('categorical')
  @classmethod
  def validate_categorical(cls, categorical: bool, info: ValidationInfo) -> bool:
    """Validate the categorical field."""
    if categorical and is_float(info.data['dtype']):
      raise ValueError('Categorical fields cannot be float dtypes.')
    return categorical

  @model_validator(mode='after')
  def validate_field(self) -> 'Field':
    """Validate the field model."""
    if self.fields and self.repeated_field:
      raise ValueError('Both "fields" and "repeated_field" should not be defined')

    if self.dtype and self.repeated_field:
      raise ValueError('dtype and repeated_field cannot both be defined.')

    if not self.repeated_field and not self.fields and not self.dtype:
      raise ValueError('One of "fields", "repeated_field", or "dtype" should be defined')

    return self

  def __str__(self) -> str:
    return _str_field(self, indent=0)

  def __repr__(self) -> str:
    return f' {self.__class__.__name__}::{self.model_dump_json(exclude_none=True, indent=2)}'


class Schema(BaseModel):
  """Database schema."""

  fields: dict[str, Field]
  # Cached leafs.
  _leafs: Optional[dict[PathTuple, Field]] = None
  # Cached flat list of all the fields.
  _all_fields: Optional[list[tuple[PathTuple, Field]]] = None
  model_config = ConfigDict(arbitrary_types_allowed=True)

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

  def __eq__(self, other: Any) -> bool:
    if not isinstance(other, Schema):
      return False
    return self.model_dump() == other.model_dump()

  def has_field(self, path: PathTuple) -> bool:
    """Returns if the field is found at the given path."""
    if path == (ROWID,):
      return True
    f = cast(Field, self)
    for path_part in path:
      if f.fields:
        f = cast(Field, f.fields.get(path_part))
        if not f:
          return False
      elif f.repeated_field:
        if path_part != PATH_WILDCARD:
          return False
        f = f.repeated_field
      elif f.dtype and isinstance(f.dtype, MapType) and f.dtype.key_type == STRING:
        f = Field(dtype=f.dtype.value_type)
      else:
        return False
    return True

  def get_field(self, path: PathTuple) -> Field:
    """Returns the field at the given path."""
    if path == (ROWID,):
      return Field(dtype=STRING)
    f = cast(Field, self)
    for name in path:
      if f.fields:
        if name not in f.fields:
          raise ValueError(f'Path {path} not found in schema')
        f = f.fields[name]
      elif f.repeated_field:
        if name != PATH_WILDCARD:
          raise ValueError(f'Invalid path for a schema field: {path}')
        f = f.repeated_field
      elif f.dtype and isinstance(f.dtype, MapType) and f.dtype.key_type == STRING:
        f = Field(dtype=f.dtype.value_type)
      else:
        raise ValueError(f'Invalid path for a schema field: {path}')
    return f

  def __str__(self) -> str:
    return _str_fields(self.fields, indent=0)

  def __repr__(self) -> str:
    return self.model_dump_json(exclude_none=True, indent=2)


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
  label: Optional[str] = None,
  map: Optional[MapInfo] = None,
) -> Field:
  """Parse a field-like object to a Field object."""
  field = _parse_field_like(fields or {}, dtype)
  if signal:
    field.signal = signal
  if map:
    field.map = map
  if label:
    field.label = label
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
  return {SPAN_KEY: {TEXT_SPAN_START_FEATURE: start, TEXT_SPAN_END_FEATURE: end}, **metadata}


def lilac_embedding(start: int, end: int, embedding: Optional[np.ndarray]) -> Item:
  """Creates a lilac embedding item, representing a vector with a pointer to a slice of text."""
  # Cast to int; we've had issues where start/end were np.int64, which caused downstream sadness.
  return lilac_span(int(start), int(end), {EMBEDDING_KEY: embedding})


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


def column_paths_match(path_match: Path, specific_path: Path) -> bool:
  """Test whether two column paths match.

  Args:
    path_match: A column path that contains wildcards, and sub-paths. This path will be used for
       testing the second specific path.
    specific_path: A column path that specifically identifies an field.

  Returns:
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


class ImageInfo(BaseModel):
  """Info about an individual image."""

  path: Path


def normalize_path(path: Path) -> PathTuple:
  """Normalizes a dot seperated path, but ignores dots inside quotes, like regular SQL.

  Examples:
  - 'a.b.c' will be parsed as ('a', 'b', 'c').
  - '"a.b".c' will be parsed as ('a.b', 'c').
  - '"a".b.c' will be parsed as ('a', 'b', 'c').
  """
  if isinstance(path, str):
    return tuple(next(csv.reader(io.StringIO(path), delimiter='.')))
  return path


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
  return f' {field.dtype}'


def dtype_to_arrow_schema(dtype: Optional[DataType]) -> Union[pa.Schema, pa.DataType]:
  """Convert the dtype to an arrow dtype."""
  if dtype == STRING:
    return pa.string()
  elif dtype == BOOLEAN:
    return pa.bool_()
  elif dtype == FLOAT16:
    return pa.float16()
  elif dtype == FLOAT32:
    return pa.float32()
  elif dtype == FLOAT64:
    return pa.float64()
  elif dtype == INT8:
    return pa.int8()
  elif dtype == INT16:
    return pa.int16()
  elif dtype == INT32:
    return pa.int32()
  elif dtype == INT64:
    return pa.int64()
  elif dtype == UINT8:
    return pa.uint8()
  elif dtype == UINT16:
    return pa.uint16()
  elif dtype == UINT32:
    return pa.uint32()
  elif dtype == UINT64:
    return pa.uint64()
  elif dtype == BINARY:
    return pa.binary()
  elif dtype == TIME:
    return pa.time64()
  elif dtype == DATE:
    return pa.date64()
  elif dtype == TIMESTAMP:
    return pa.timestamp('us')
  elif dtype == INTERVAL:
    return pa.duration('us')
  elif dtype == EMBEDDING:
    # We reserve an empty column for embeddings in parquet files so they can be queried.
    # The values are *not* filled out. If parquet and duckdb support embeddings in the future, we
    # can set this dtype to the relevant pyarrow type.
    return pa.null()
  elif dtype == STRING_SPAN:
    return pa.struct(
      {
        SPAN_KEY: pa.struct(
          {TEXT_SPAN_START_FEATURE: pa.int32(), TEXT_SPAN_END_FEATURE: pa.int32()}
        )
      }
    )
  elif dtype == NULL:
    return pa.null()
  elif dtype is None:
    return pa.null()
  elif dtype.type == 'map':
    map_dtype = cast(MapType, dtype)
    return pa.map_(
      dtype_to_arrow_schema(map_dtype.key_type), dtype_to_arrow_schema(map_dtype.value_type)
    )
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
        arrow_schema = dtype_to_arrow_schema(field.dtype)
      else:
        arrow_schema = _schema_to_arrow_schema_impl(field)
      arrow_fields[name] = arrow_schema

    if isinstance(schema, Schema):
      return pa.schema(arrow_fields)
    else:
      # When nodes have both dtype and children, we add __value__ alongside the fields.
      if schema.dtype:
        value_schema = dtype_to_arrow_schema(schema.dtype)
        if schema.dtype == STRING_SPAN:
          arrow_fields[SPAN_KEY] = value_schema[SPAN_KEY].type
        else:
          arrow_fields[VALUE_KEY] = value_schema

      return pa.struct(arrow_fields)

  field = cast(Field, schema)
  if field.repeated_field:
    return pa.list_(_schema_to_arrow_schema_impl(field.repeated_field))

  return dtype_to_arrow_schema(field.dtype)


def arrow_dtype_to_dtype(arrow_dtype: pa.DataType) -> DataType:
  """Convert arrow dtype to our dtype."""
  # Ints.
  if arrow_dtype == pa.int8():
    return INT8
  elif arrow_dtype == pa.int16():
    return INT16
  elif arrow_dtype == pa.int32():
    return INT32
  elif arrow_dtype == pa.int64():
    return INT64
  elif arrow_dtype == pa.uint8():
    return UINT8
  elif arrow_dtype == pa.uint16():
    return UINT16
  elif arrow_dtype == pa.uint32():
    return UINT32
  elif arrow_dtype == pa.uint64():
    return UINT64
  # Floats.
  elif arrow_dtype == pa.float16():
    return FLOAT16
  elif arrow_dtype == pa.float32():
    return FLOAT32
  elif arrow_dtype == pa.float64():
    return FLOAT64
  # Time.
  elif pa.types.is_time(arrow_dtype):
    return TIME
  elif pa.types.is_date(arrow_dtype):
    return DATE
  elif pa.types.is_timestamp(arrow_dtype):
    return TIMESTAMP
  elif pa.types.is_duration(arrow_dtype):
    return INTERVAL
  # Others.
  elif arrow_dtype == pa.string():
    return STRING
  elif pa.types.is_binary(arrow_dtype) or pa.types.is_fixed_size_binary(arrow_dtype):
    return BINARY
  elif pa.types.is_boolean(arrow_dtype):
    return BOOLEAN
  elif arrow_dtype == pa.null():
    return NULL
  elif pa.types.is_map(arrow_dtype):
    return MapType(
      type='map',
      key_type=arrow_dtype_to_dtype(arrow_dtype.key_type),
      value_type=arrow_dtype_to_dtype(arrow_dtype.item_type),
    )
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
    dtype: Optional[DataType] = None

    # Check for the span key, and start and end keys.
    if schema.get_field_index(SPAN_KEY) != -1 and not isinstance(schema, pa.Schema):
      span_schema = schema[SPAN_KEY].type
      if (
        isinstance(span_schema, (pa.Schema, pa.StructType))
        and span_schema.get_field_index(TEXT_SPAN_START_FEATURE) != -1
        and span_schema.get_field_index(TEXT_SPAN_END_FEATURE) != -1
        and pa.types.is_integer(span_schema[TEXT_SPAN_START_FEATURE].type)
        and pa.types.is_integer(span_schema[TEXT_SPAN_END_FEATURE].type)
      ):
        dtype = STRING_SPAN

    fields: dict[str, Field] = {
      field.name: cast(Field, _arrow_schema_to_schema_impl(field.type))
      for field in schema
      if field.name != SPAN_KEY
    }

    return (
      Schema(fields=fields) if isinstance(schema, pa.Schema) else Field(dtype=dtype, fields=fields)
    )
  elif isinstance(schema, pa.ListType):
    return Field(repeated_field=cast(Field, _arrow_schema_to_schema_impl(schema.value_field.type)))
  else:
    return Field(dtype=arrow_dtype_to_dtype(schema))


def is_float(dtype: DataType) -> bool:
  """Check if a dtype is a float dtype."""
  return dtype in [FLOAT16, FLOAT32, FLOAT64]


def is_integer(dtype: DataType) -> bool:
  """Check if a dtype is an integer dtype."""
  return dtype in [
    INT8,
    INT16,
    INT32,
    INT64,
    UINT8,
    UINT16,
    UINT32,
    UINT64,
  ]


def is_temporal(dtype: DataType) -> bool:
  """Check if a dtype is a temporal dtype."""
  return dtype in [TIME, DATE, TIMESTAMP, INTERVAL]


def is_ordinal(dtype: DataType) -> bool:
  """Check if a dtype is an ordinal dtype."""
  return is_float(dtype) or is_integer(dtype) or is_temporal(dtype)


def _infer_dtype(value: Item) -> DataType:
  if isinstance(value, str):
    return STRING
  elif isinstance(value, bool):
    return BOOLEAN
  elif isinstance(value, bytes):
    return BINARY
  elif isinstance(value, float):
    return FLOAT32
  elif isinstance(value, int):
    return INT32
  elif isinstance(value, datetime):
    return TIMESTAMP
  else:
    raise ValueError(f'Cannot infer dtype of primitive value: {value}')


def _infer_field(item: Item, diallow_pedals: bool = False) -> Field:
  """Infer the schema from the items."""
  if isinstance(item, dict):
    fields: dict[str, Field] = {}
    for k, v in item.items():
      fields[k] = _infer_field(cast(Item, v))
    dtype = None
    if VALUE_KEY in fields:
      dtype = fields[VALUE_KEY].dtype
      del fields[VALUE_KEY]
    elif SPAN_KEY in fields:
      dtype = STRING_SPAN
      del fields[SPAN_KEY]
    if not fields:
      # The object is an empty dict. We need a dummy child to represent this with parquet.
      return Field(fields={'__empty__': Field(dtype=NULL)})
    return Field(fields=fields, dtype=dtype)
  elif is_primitive(item):
    return Field(dtype=_infer_dtype(item))
  elif isinstance(item, list):
    inferred_fields = [_infer_field(subitem) for subitem in item]
    merged_field = merge_fields(inferred_fields, diallow_pedals)
    return Field(repeated_field=merged_field)
  else:
    raise ValueError(f'Cannot infer schema of item: {item}')


def infer_schema(items: list[Item]) -> Schema:
  """Infer the schema from a list of items."""
  merged_field = merge_fields(
    [_infer_field(item, diallow_pedals=True) for item in items], disallow_pedals=True
  )
  if not merged_field.fields:
    raise ValueError(f'Failed to infer schema. Got {merged_field}')
  return Schema(fields=merged_field.fields)


def _print_fields(field: Field, destination: Field) -> None:
  log('New field:')
  log(field)
  log('Destination field:')
  log(destination)


def _merge_field_into(field: Field, destination: Field, disallow_pedals: bool = False) -> None:
  destination.signal = destination.signal or field.signal
  destination.map = destination.map or field.map
  if field.fields:
    if destination.repeated_field:
      _print_fields(field, destination)
      raise ValueError(
        'Failed to merge fields. New field has fields, but destination is ' 'repeated'
      )
    if disallow_pedals and destination.dtype:
      _print_fields(field, destination)
      raise ValueError('Failed to merge fields. New field has fields, but destination has dtype')
    destination.fields = destination.fields or {}
    if destination.dtype == NULL:
      destination.dtype = None
    for field_name, subfield in field.fields.items():
      if field_name not in destination.fields:
        destination.fields[field_name] = subfield.model_copy(deep=True)
      else:
        _merge_field_into(subfield, destination.fields[field_name], disallow_pedals)
  elif field.repeated_field:
    if destination.fields:
      _print_fields(field, destination)
      raise ValueError(
        'Failed to merge fields. New field is repeated, but destination has ' 'fields'
      )
    if destination.dtype:
      if destination.dtype != NULL:
        _print_fields(field, destination)
        raise ValueError(
          'Failed to merge fields. New field is repeated, but destination has ' 'dtype'
        )
      else:
        destination.dtype = None
        destination.repeated_field = field.repeated_field.model_copy(deep=True)
        return
    if not destination.repeated_field:
      _print_fields(field, destination)
      raise ValueError('Failed to merge fields. New field is repeated, but destination is not')
    _merge_field_into(field.repeated_field, destination.repeated_field, disallow_pedals)

  if field.dtype:
    if field.dtype == NULL:
      return
    if destination.repeated_field:
      _print_fields(field, destination)
      raise ValueError(
        'Failed to merge fields. New field has dtype, but destination is ' 'repeated'
      )
    if disallow_pedals and destination.fields:
      _print_fields(field, destination)
      raise ValueError('Failed to merge fields. New field has dtype, but destination has fields')

    if (
      destination.dtype != NULL
      and destination.dtype is not None
      and destination.dtype != field.dtype
    ):
      raise ValueError(
        f'Failed to merge fields. New field has dtype {field.dtype}, but '
        f'destination has dtype {destination.dtype}'
      )
    destination.dtype = field.dtype


def merge_fields(fields: Sequence[Field], disallow_pedals: bool = False) -> Field:
  """Merge a list of fields.

  Args:
    fields: A list of fields to merge.
    disallow_pedals: If True, merging a field with dtype into a field with fields will raise an
                     error.
  """
  if not fields:
    return Field(dtype=NULL)
  merged_field = fields[0].model_copy(deep=True)
  for field in fields[1:]:
    _merge_field_into(field, merged_field, disallow_pedals)
  return merged_field


def merge_schemas(schemas: Sequence[Union[Schema, Field]]) -> Schema:
  """Merge a list of schemas."""
  merged_field = merge_fields([Field(fields=s.fields) for s in schemas])
  assert merged_field.fields, 'Merged field should have fields'
  return Schema(fields=merged_field.fields)
