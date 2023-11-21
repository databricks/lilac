"""Tests for the paquet source."""

import os
import pathlib

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from pydantic import ValidationError

from ..schema import FLOAT32, STRING, MapType, field, schema
from ..source import SourceSchema
from ..test_utils import retrieve_parquet_rows
from ..utils import chunks
from .parquet_source import ParquetSource


def test_simple_rows(tmp_path: pathlib.Path) -> None:
  table = pa.Table.from_pylist(
    [{'name': 'a', 'age': 1}, {'name': 'b', 'age': 2}, {'name': 'c', 'age': 3}]
  )

  out_file = os.path.join(tmp_path, 'test.parquet')
  pq.write_table(table, out_file)

  source = ParquetSource(filepaths=[out_file])
  source.setup()
  source_schema = source.source_schema()
  assert source_schema == SourceSchema(
    fields=schema({'name': 'string', 'age': 'int64'}).fields, num_items=3
  )
  manifest = source.load_to_parquet(str(tmp_path), task_step_id=None)
  items = retrieve_parquet_rows(tmp_path, manifest)
  assert items == [{'name': 'a', 'age': 1}, {'name': 'b', 'age': 2}, {'name': 'c', 'age': 3}]


def test_map_dtype(tmp_path: pathlib.Path) -> None:
  # Create data for the table
  data = {
    'column': [
      {'a': 1.0, 'b': 2.0},
      {'b': 2.5},
      {'a': 3.0, 'c': 3.5},
    ]
  }
  # Create a table with a single column of type map<string, float>.
  table = pa.table(data, schema=pa.schema([('column', pa.map_(pa.string(), pa.float32()))]))

  out_file = os.path.join(tmp_path, 'test.parquet')
  pq.write_table(table, out_file)

  source = ParquetSource(filepaths=[out_file])
  source.setup()
  source_schema = source.source_schema()
  assert source_schema == SourceSchema(
    fields=schema({'column': field(MapType(key_type=STRING, value_type=FLOAT32))}).fields,
    num_items=3,
  )
  manifest = source.load_to_parquet(str(tmp_path), task_step_id=None)
  items = retrieve_parquet_rows(tmp_path, manifest)
  assert items == [
    {'column': [('a', 1.0), ('b', 2.0)]},
    {'column': [('b', 2.5)]},
    {'column': [('a', 3.0), ('c', 3.5)]},
  ]


def test_single_shard_with_sampling(tmp_path: pathlib.Path) -> None:
  source_items = [{'name': 'a', 'age': 1}, {'name': 'b', 'age': 2}, {'name': 'c', 'age': 3}]
  table = pa.Table.from_pylist(source_items)

  out_file = os.path.join(tmp_path, 'test.parquet')
  pq.write_table(table, out_file)

  # Test sampling with different sample sizes, including sample size > num_items.
  for sample_size in range(1, 5):
    source = ParquetSource(filepaths=[out_file], sample_size=sample_size)
    source.setup()
    manifest = source.load_to_parquet(str(tmp_path), task_step_id=None)
    items = retrieve_parquet_rows(tmp_path, manifest)
    assert len(items) == min(sample_size, len(source_items))


def test_single_shard_pseudo_shuffle(tmp_path: pathlib.Path) -> None:
  source_items = [{'name': 'a', 'age': 1}, {'name': 'b', 'age': 2}, {'name': 'c', 'age': 3}]
  table = pa.Table.from_pylist(source_items)

  out_file = os.path.join(tmp_path, 'test.parquet')
  pq.write_table(table, out_file)

  # Test sampling with different sample sizes, including sample size > num_items.
  for sample_size in range(1, 5):
    source = ParquetSource(filepaths=[out_file], sample_size=sample_size, pseudo_shuffle=True)
    source.setup()
    manifest = source.load_to_parquet(str(tmp_path), task_step_id=None)
    items = retrieve_parquet_rows(tmp_path, manifest)
    assert len(items) == min(sample_size, len(source_items))


def test_multi_shard(tmp_path: pathlib.Path) -> None:
  source_items = [{'name': 'a', 'age': 1}, {'name': 'b', 'age': 2}, {'name': 'c', 'age': 3}]
  for i, item in enumerate(source_items):
    table = pa.Table.from_pylist([item])
    out_file = tmp_path / f'test-{i}.parquet'
    pq.write_table(table, out_file)

  source = ParquetSource(filepaths=[str(tmp_path / 'test-*.parquet')])
  source.setup()
  manifest = source.load_to_parquet(str(tmp_path), task_step_id=None)
  items = retrieve_parquet_rows(tmp_path, manifest)
  items.sort(key=lambda x: x['name'])
  assert items == source_items


def test_multi_shard_sample(tmp_path: pathlib.Path) -> None:
  source_items = [{'name': 'a', 'age': 1}, {'name': 'b', 'age': 2}, {'name': 'c', 'age': 3}]
  for i, item in enumerate(source_items):
    table = pa.Table.from_pylist([item])
    out_file = tmp_path / f'test-{i}.parquet'
    pq.write_table(table, out_file)

  # Test sampling with different sample sizes, including sample size > num_items.
  for sample_size in range(1, 5):
    source = ParquetSource(filepaths=[str(tmp_path / 'test-*.parquet')], sample_size=sample_size)
    source.setup()
    manifest = source.load_to_parquet(str(tmp_path), task_step_id=None)
    items = retrieve_parquet_rows(tmp_path, manifest)
    assert len(items) == min(sample_size, len(source_items))


def test_multi_shard_approx_shuffle(tmp_path: pathlib.Path) -> None:
  source_items = [{'name': 'a', 'age': 1}, {'name': 'b', 'age': 2}, {'name': 'c', 'age': 3}]
  for i, item in enumerate(source_items):
    table = pa.Table.from_pylist([item])
    out_file = tmp_path / f'test-{i}.parquet'
    pq.write_table(table, out_file)

  # Test sampling with different sample sizes, including sample size > num_items.
  for sample_size in range(1, 5):
    source = ParquetSource(
      filepaths=[str(tmp_path / 'test-*.parquet')],
      pseudo_shuffle=True,
      sample_size=sample_size,
    )
    source.setup()
    manifest = source.load_to_parquet(str(tmp_path), task_step_id=None)
    items = retrieve_parquet_rows(tmp_path, manifest)
    assert len(items) == min(sample_size, len(source_items))


def test_uniform_shards_pseudo_shuffle(tmp_path: pathlib.Path) -> None:
  source_items = [{'index': i} for i in range(100)]
  for i, chunk in enumerate(chunks(source_items, 10)):
    table = pa.Table.from_pylist(chunk)
    out_file = tmp_path / f'test-{i}.parquet'
    pq.write_table(table, out_file)

  source = ParquetSource(
    filepaths=[str(tmp_path / 'test-*.parquet')], pseudo_shuffle=True, sample_size=20
  )
  source.setup()
  manifest = source.load_to_parquet(str(tmp_path), task_step_id=None)
  items = retrieve_parquet_rows(tmp_path, manifest)
  assert len(items) == 20


def test_nonuniform_shards_pseudo_shuffle(tmp_path: pathlib.Path) -> None:
  source_items = [{'index': i} for i in range(100)]
  shard_sizes = [49, 1, 40, 10]
  for i, shard_size in enumerate(shard_sizes):
    chunk = source_items[:shard_size]
    source_items = source_items[shard_size:]
    table = pa.Table.from_pylist(chunk)
    out_file = tmp_path / f'test-{i}.parquet'
    pq.write_table(table, out_file)

  source = ParquetSource(
    filepaths=[str(tmp_path / 'test-*.parquet')], pseudo_shuffle=True, sample_size=20
  )
  source.setup()
  manifest = source.load_to_parquet(str(tmp_path), task_step_id=None)
  items = retrieve_parquet_rows(tmp_path, manifest)
  assert len(items) == 20


def test_sampling_with_seed(tmp_path: pathlib.Path) -> None:
  source_items = [{'index': i} for i in range(100)]
  for i, chunk in enumerate(chunks(source_items, 10)):
    table = pa.Table.from_pylist(chunk)
    out_file = tmp_path / f'test-{i}.parquet'
    pq.write_table(table, out_file)

  source = ParquetSource(filepaths=[str(tmp_path / 'test-*.parquet')], sample_size=20, seed=42)
  source.setup()
  manifest = source.load_to_parquet(str(tmp_path), task_step_id=None)
  items = retrieve_parquet_rows(tmp_path, manifest)
  assert len(items) == 20


def test_approx_shuffle_with_seed(tmp_path: pathlib.Path) -> None:
  source_items = [{'index': i} for i in range(100)]
  for i, chunk in enumerate(chunks(source_items, 10)):
    table = pa.Table.from_pylist(chunk)
    out_file = tmp_path / f'test-{i}.parquet'
    pq.write_table(table, out_file)

  source = ParquetSource(
    filepaths=[str(tmp_path / 'test-*.parquet')], pseudo_shuffle=True, sample_size=20, seed=42
  )
  source.setup()
  manifest = source.load_to_parquet(str(tmp_path), task_step_id=None)
  items = retrieve_parquet_rows(tmp_path, manifest)
  assert len(items) == 20


def test_validation() -> None:
  with pytest.raises(ValidationError, match='filepaths must be non-empty'):
    ParquetSource(filepaths=[])

  with pytest.raises(ValidationError, match='sample_size must be greater than 0'):
    ParquetSource(filepaths=['gs://lilac/test.parquet'], sample_size=0)
