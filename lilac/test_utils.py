"""Utilities for unit tests."""

import os
import pathlib
import uuid
from typing import Union

import pyarrow.parquet as pq

from .schema import ROWID, DataType, Field, Item, Schema, schema_to_arrow_schema


def read_items(data_dir: Union[str, pathlib.Path], filepaths: list[str],
               schema: Schema) -> list[Item]:
  """Read the source items from a dataset output directory."""
  items: list[Item] = []
  schema.fields[ROWID] = Field(dtype=DataType.STRING)
  for filepath in filepaths:
    items.extend(
      pq.read_table(os.path.join(data_dir, filepath),
                    schema=schema_to_arrow_schema(schema)).to_pylist())
  return items


def fake_uuid(id: bytes) -> uuid.UUID:
  """Create a test UUID."""
  return uuid.UUID((id * 16).hex())
