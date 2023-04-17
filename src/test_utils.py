"""Utilities for unit tests."""

import os
import pathlib
from typing import Union

import pyarrow.parquet as pq

from .schema import Item, Schema, schema_to_arrow_schema


def read_items(data_dir: Union[str, pathlib.Path], filepaths: list[str],
               schema: Schema) -> list[Item]:
  """Read the source items from a dataset output directory."""
  items: list[Item] = []
  for filepath in filepaths:
    items.extend(
        pq.read_table(os.path.join(data_dir, filepath),
                      schema=schema_to_arrow_schema(schema)).to_pylist())
  return items
