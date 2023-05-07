"""Tests utils of for db_dataset_test."""
import os
import pathlib
from typing import Optional, Type, cast

from ..schema import (
  MANIFEST_FILENAME,
  PARQUET_FILENAME_PREFIX,
  DataType,
  Field,
  Item,
  ItemValue,
  Schema,
  SourceManifest,
)
from ..utils import get_dataset_output_dir, open_file
from .dataset_utils import is_primitive, write_items_to_parquet
from .db_dataset import DatasetDB

TEST_NAMESPACE = 'test_namespace'
TEST_DATASET_NAME = 'test_dataset'


def _infer_dtype(value: ItemValue) -> DataType:
  if isinstance(value, str):
    return DataType.STRING
  elif isinstance(value, bool):
    return DataType.BOOLEAN
  elif isinstance(value, bytes):
    return DataType.BINARY
  elif isinstance(value, float):
    return DataType.FLOAT32
  elif isinstance(value, int):
    return DataType.INT32
  else:
    raise ValueError(f'Cannot infer dtype of primitive value: {value}')


def _infer_field(item: Item) -> Field:
  """Infer the schema from the items."""
  if isinstance(item, dict):
    fields: dict[str, Field] = {}
    for k, v in item.items():
      fields[k] = _infer_field(cast(Item, v))
    return Field(fields=fields)
  elif is_primitive(item):
    return Field(dtype=_infer_dtype(item))
  elif isinstance(item, list):
    return Field(repeated_field=_infer_field(item[0]))
  else:
    raise ValueError(f'Cannot infer schema of item: {item}')


def _infer_schema(items: list[Item]) -> Schema:
  """Infer the schema from the items."""
  schema = Schema(fields={})
  for item in items:
    field = _infer_field(item)
    if not field.fields:
      raise ValueError(f'Invalid schema of item. Expected an object, but got: {item}')
    schema.fields = {**schema.fields, **field.fields}
  return schema


def _parse_dtype_like(dtype_like: str) -> DataType:
  if dtype_like == 'int32':
    return DataType.INT32
  elif dtype_like == 'float32':
    return DataType.FLOAT32
  elif dtype_like == 'string':
    return DataType.STRING
  elif dtype_like == 'boolean':
    return DataType.BOOLEAN
  elif dtype_like == 'binary':
    return DataType.BINARY
  else:
    raise ValueError(f'Cannot parse dtype like: {dtype_like}')


def _parse_field_like(field_like: object) -> Field:
  if isinstance(field_like, dict):
    fields: dict[str, Field] = {}
    for k, v in field_like.items():
      fields[k] = _parse_field_like(v)
    return Field(fields=fields)
  elif isinstance(field_like, str):
    return Field(dtype=_parse_dtype_like(field_like))
  elif isinstance(field_like, list):
    return Field(repeated_field=_parse_field_like(field_like[0]))
  else:
    raise ValueError(f'Cannot parse field like: {field_like}')


def schema_like(schema_like: object) -> Schema:
  """Parse a schema-like object to a Schema object."""
  field = _parse_field_like(schema_like)
  return Schema(fields=field.fields)


def make_db(db_cls: Type[DatasetDB],
            tmp_path: pathlib.Path,
            items: list[Item],
            schema: Optional[Schema] = None) -> DatasetDB:
  """Create a test database."""
  schema = schema or _infer_schema(items)
  _write_items(tmp_path, TEST_DATASET_NAME, items, schema)
  return db_cls(TEST_NAMESPACE, TEST_DATASET_NAME)


def _write_items(tmpdir: pathlib.Path, dataset_name: str, items: list[Item],
                 schema: Schema) -> None:
  """Write the items JSON to the dataset format: manifest.json and parquet files."""
  source_dir = get_dataset_output_dir(str(tmpdir), TEST_NAMESPACE, dataset_name)
  os.makedirs(source_dir)

  simple_parquet_files, _ = write_items_to_parquet(
    items, source_dir, schema, filename_prefix=PARQUET_FILENAME_PREFIX, shard_index=0, num_shards=1)
  manifest = SourceManifest(files=[simple_parquet_files], data_schema=schema)
  with open_file(os.path.join(source_dir, MANIFEST_FILENAME), 'w') as f:
    f.write(manifest.json(indent=2, exclude_none=True))
