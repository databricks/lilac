"""Tests utils of for db_dataset_test."""
import os
import pathlib
from typing import Type

from ..schema import (
    MANIFEST_FILENAME,
    PARQUET_FILENAME_PREFIX,
    Item,
    Schema,
    SourceManifest,
)
from ..utils import get_dataset_output_dir, open_file, write_items_to_parquet
from .db_dataset import DatasetDB

TEST_NAMESPACE = 'test_namespace'
TEST_DATASET_NAME = 'test_dataset'


def make_db(db_cls: Type[DatasetDB], tmp_path: pathlib.Path, items: list[Item],
            schema: Schema) -> DatasetDB:
  """Create a test database."""
  _write_items(tmp_path, TEST_DATASET_NAME, items, schema)
  return db_cls(TEST_NAMESPACE, TEST_DATASET_NAME)


def _write_items(tmpdir: pathlib.Path, dataset_name: str, items: list[Item],
                 schema: Schema) -> None:
  """Write the items JSON to the dataset format: manifest.json and parquet files."""
  source_dir = get_dataset_output_dir(str(tmpdir), TEST_NAMESPACE, dataset_name)
  os.makedirs(source_dir)
  parquet_items: list[Item] = []
  for item in items:
    parquet_items.append(item.copy())

  simple_parquet_files, _ = write_items_to_parquet(parquet_items,
                                                   source_dir,
                                                   schema,
                                                   filename_prefix=PARQUET_FILENAME_PREFIX,
                                                   shard_index=0,
                                                   num_shards=1)
  manifest = SourceManifest(files=[simple_parquet_files], data_schema=schema)
  with open_file(os.path.join(source_dir, MANIFEST_FILENAME), 'w') as f:
    f.write(manifest.json(indent=2, exclude_none=True))
