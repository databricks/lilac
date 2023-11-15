"""Utilities for DatasetDuckDB."""

import json
import os
import secrets
from collections.abc import Iterable
from typing import Optional

from ..env import env
from ..parquet_writer import ParquetWriter
from ..schema import (
  ROWID,
  DataType,
  Field,
  Item,
  Schema,
  schema_to_arrow_schema,
)
from ..utils import open_file
from .dataset_utils import get_parquet_filename


def write_items_to_cached_jsonl(
  items: Iterable[Item],
  key: str,
  output_dir: str,
  filename_prefix: str,
  overwrite: bool,
  shard_index: int,
  num_shards: int,
  schema: Optional[Schema] = None,
) -> tuple[str, int]:
  """Writes an iterable of items to a cached jsonl file, caching the output for re-runs."""
  if schema:
    schema = schema.model_copy(deep=True)

    # Add a rowid column.
    schema.fields[ROWID] = Field(dtype=DataType.STRING)

  arrow_schema = schema_to_arrow_schema(schema)
  out_filename = get_parquet_filename(filename_prefix, shard_index, num_shards)
  filepath = os.path.join(output_dir, out_filename)
  f = open_file(filepath, mode='wb')
  writer = ParquetWriter(schema)
  writer.open(f)
  debug = env('DEBUG', False)
  num_items = 0
  for item in items:
    # Add a rowid column.
    if ROWID not in item:
      item[ROWID] = secrets.token_urlsafe(nbytes=12)  # 16 base64 characters.
    if debug:
      try:
        _validate(item, arrow_schema)
      except Exception as e:
        raise ValueError(f'Error validating item: {json.dumps(item)}') from e
    writer.write(item)
    num_items += 1
  writer.close()
  f.close()
  return out_filename, num_items


def reshard_jsonl_to_parquet(jsonl_filenames: list[str]):
  pass
