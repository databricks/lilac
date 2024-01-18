"""Tests utils of for dataset_test."""
import json
import os
import pathlib
from copy import deepcopy
from datetime import datetime
from typing import Any, ClassVar, Optional, Type, cast

import numpy as np
from typing_extensions import Protocol

from ..config import DatasetConfig
from ..embeddings.vector_store import VectorDBIndex
from ..project import add_project_dataset_config, create_project, update_project_dataset_settings
from ..schema import (
  BINARY,
  BOOLEAN,
  FLOAT32,
  INT32,
  MANIFEST_FILENAME,
  NULL,
  PARQUET_FILENAME_PREFIX,
  ROWID,
  SPAN_KEY,
  STRING,
  STRING_SPAN,
  TIMESTAMP,
  VALUE_KEY,
  DataType,
  Field,
  Item,
  PathKey,
  Schema,
  merge_fields,
)
from ..source import Source, SourceManifest
from ..utils import get_dataset_output_dir, is_primitive, open_file
from .dataset import Dataset, default_settings
from .dataset_utils import write_items_to_parquet

TEST_NAMESPACE = 'test_namespace'
TEST_DATASET_NAME = 'test_dataset'


class TestDataMaker(Protocol):
  """A function that creates a test dataset."""

  def __call__(self, items: list[Item], schema: Optional[Schema] = None) -> Dataset:
    """Create a test dataset."""
    ...


class TestSource(Source):
  """Test source that does nothing."""

  name: ClassVar[str] = 'test_source'


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
      return Field(dtype=NULL)
    return Field(fields=fields, dtype=dtype)
  elif is_primitive(item):
    return Field(dtype=_infer_dtype(item))
  elif isinstance(item, list):
    inferred_fields = [_infer_field(subitem) for subitem in item]
    merged_field = merge_fields(inferred_fields, diallow_pedals)
    return Field(repeated_field=merged_field)
  else:
    raise ValueError(f'Cannot infer schema of item: {item}')


def _infer_schema(items: list[Item]) -> Schema:
  """Infer the schema from a list of items."""
  merged_field = merge_fields(
    [_infer_field(item, diallow_pedals=True) for item in items], disallow_pedals=True
  )
  if not merged_field.fields:
    raise ValueError(f'Failed to infer schema. Got {merged_field}')
  return Schema(fields=merged_field.fields)


def make_dataset(
  dataset_cls: Type[Dataset],
  tmp_path: pathlib.Path,
  items: list[Item],
  schema: Optional[Schema] = None,
) -> Dataset:
  """Create a test dataset."""
  schema = schema or _infer_schema(items)
  _write_items(tmp_path, TEST_DATASET_NAME, items, schema)
  create_project(str(tmp_path))

  config = DatasetConfig(namespace=TEST_NAMESPACE, name=TEST_DATASET_NAME, source=TestSource())
  add_project_dataset_config(config)

  dataset = dataset_cls(TEST_NAMESPACE, TEST_DATASET_NAME)
  settings = default_settings(dataset)
  update_project_dataset_settings(TEST_NAMESPACE, TEST_DATASET_NAME, settings)

  return dataset


def _write_items(
  tmpdir: pathlib.Path, dataset_name: str, items: list[Item], schema: Schema
) -> None:
  """Write the items JSON to the dataset format: manifest.json and parquet files."""
  source_dir = get_dataset_output_dir(str(tmpdir), TEST_NAMESPACE, dataset_name)
  os.makedirs(source_dir)

  # Add rowids to the items.
  items = [deepcopy(item) for item in items]
  for i, item in enumerate(items):
    item[ROWID] = str(i + 1).zfill(5)

  simple_parquet_files = write_items_to_parquet(
    items, source_dir, schema, filename_prefix=PARQUET_FILENAME_PREFIX, shard_index=0, num_shards=1
  )
  manifest = SourceManifest(files=[simple_parquet_files], data_schema=schema, source=TestSource())
  with open_file(os.path.join(source_dir, MANIFEST_FILENAME), 'w') as f:
    f.write(manifest.model_dump_json(indent=2, exclude_none=True))


def enriched_item(value: Optional[Item] = None, metadata: dict[str, Item] = {}) -> Item:
  """Wrap a value in a dict with the value key."""
  return {VALUE_KEY: value, **metadata}


def make_vector_index(
  vector_store: str, vector_dict: dict[PathKey, list[list[float]]]
) -> VectorDBIndex:
  """Make a vector index from a dictionary of vector keys to vectors."""
  embeddings: list[np.ndarray] = []
  spans: list[tuple[PathKey, list[tuple[int, int]]]] = []
  for path_key, vectors in vector_dict.items():
    vector_spans: list[tuple[int, int]] = []
    for i, vector in enumerate(vectors):
      embeddings.append(np.array(vector))
      vector_spans.append((0, 0))
    spans.append((path_key, vector_spans))

  vector_index = VectorDBIndex(vector_store)
  vector_index.add(spans, np.array(embeddings))
  return vector_index


class TestProcessLogger:
  """A simple utility for unit tests that need logging between processes and main process."""

  def __init__(self, tmp_dir: pathlib.Path):
    self.tmp_dir = tmp_dir

  def log_event(self, value: Any) -> None:
    """Logs an event to the log file for communicate between worker & test."""
    with open(os.path.join(self.tmp_dir, 'log.jsonl'), 'a') as f:
      f.write(f'{json.dumps(value)}\n')

  def clear_logs(self) -> None:
    """Clears the logs."""
    with open(os.path.join(self.tmp_dir, 'log.jsonl'), 'w') as f:
      f.write('')

  def get_logs(self) -> list[Any]:
    """Gets the logs."""
    with open(os.path.join(self.tmp_dir, 'log.jsonl'), 'r') as f:
      return [json.loads(line) for line in f.readlines()]
