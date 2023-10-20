"""Tests for the paquet source."""

import os
import pathlib

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from pydantic import ValidationError

from ..schema import schema
from ..source import SourceSchema
from .parquet_source import ParquetSource


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


def test_sampling(tmp_path: pathlib.Path) -> None:
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

  for sample_size in range(1, 4):
    source = ParquetSource(filepaths=[out_file], sample_size=sample_size)
    source.setup()
    items = list(source.process())
    assert len(items) == sample_size


def test_validation() -> None:
  with pytest.raises(ValidationError, match='filepaths must be non-empty'):
    ParquetSource(filepaths=[])

  with pytest.raises(ValidationError, match='sample_size must be greater than 0'):
    ParquetSource(filepaths=['gs://lilac/test.parquet'], sample_size=0)
