"""Tests for the paquet source."""

import os
import pathlib

import pyarrow as pa
import pyarrow.parquet as pq

from ..schema import schema
from .parquet_source import ParquetSource
from .source import SourceSchema


def test_simple_rows(tmp_path: pathlib.Path) -> None:
  table = pa.Table.from_pylist([{
    'name': 'a',
    'age': 1
  }, {
    'name': 'b',
    'age': 2
  }, {
    'name': 'c',
    'age': 3
  }])

  out_file = os.path.join(tmp_path, 'test.parquet')
  pq.write_table(table, out_file)

  source = ParquetSource(filepaths=[out_file])
  source.setup()
  source_schema = source.source_schema()
  assert source_schema == SourceSchema(
    fields=schema({
      'name': 'string',
      'age': 'int64'
    }).fields, num_items=3)

  items = list(source.process())
  assert items == [{'name': 'a', 'age': 1}, {'name': 'b', 'age': 2}, {'name': 'c', 'age': 3}]
