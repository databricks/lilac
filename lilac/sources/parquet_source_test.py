"""Tests for the paquet source."""

import os
import pathlib

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from pydantic import ValidationError

from ..config import DatasetConfig
from ..load_dataset import create_dataset
from ..project import create_project_and_set_env
from ..schema import STRING, Field, MapType, field, schema
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
    fields=schema({'name': 'string', 'age': 'int64'}).fields, num_items=None
  )
  manifest = source.load_to_parquet(str(tmp_path), task_id=None)
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
    fields=schema({'column': field(MapType(key_type=STRING, value_field=field('float32')))}).fields,
    num_items=None,
  )
  manifest = source.load_to_parquet(str(tmp_path), task_id=None)
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
    manifest = source.load_to_parquet(str(tmp_path), task_id=None)
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
    manifest = source.load_to_parquet(str(tmp_path), task_id=None)
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
  manifest = source.load_to_parquet(str(tmp_path), task_id=None)
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
    manifest = source.load_to_parquet(str(tmp_path), task_id=None)
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
    manifest = source.load_to_parquet(str(tmp_path), task_id=None)
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
  manifest = source.load_to_parquet(str(tmp_path), task_id=None)
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
  manifest = source.load_to_parquet(str(tmp_path), task_id=None)
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
  manifest = source.load_to_parquet(str(tmp_path), task_id=None)
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
  manifest = source.load_to_parquet(str(tmp_path), task_id=None)
  items = retrieve_parquet_rows(tmp_path, manifest)
  assert len(items) == 20


def test_validation() -> None:
  with pytest.raises(ValidationError, match='filepaths must be non-empty'):
    ParquetSource(filepaths=[])

  with pytest.raises(ValidationError, match='sample_size must be greater than 0'):
    ParquetSource(filepaths=['gs://lilac/test.parquet'], sample_size=0)


def test_parquet_with_map_of_string_to_array_of_ints(tmp_path: pathlib.Path) -> None:
  create_project_and_set_env(str(tmp_path))
  arrow_schema = pa.schema(
    {
      'id': pa.int32(),
      'name': pa.map_(pa.string(), pa.list_(pa.int32())),
    }
  )
  table = pa.Table.from_pylist(
    [
      {'id': 0, 'name': {'key1': [1, 2, 3]}},
      {'id': 1, 'name': {'key2': [2, 3]}},
      {'id': 2, 'name': {'key1': [3, 4], 'key2': [5, 6]}},
    ],
    schema=arrow_schema,
  )
  out_file = os.path.join(tmp_path, 'test.parquet')
  pq.write_table(table, out_file)
  config = DatasetConfig(
    namespace='local', name='parquet_with_map', source=ParquetSource(filepaths=[out_file])
  )
  dataset = create_dataset(config)

  expected_map_dtype = MapType(key_type=STRING, value_field=Field(repeated_field=field('int32')))
  assert dataset.manifest().data_schema == schema(
    {
      'name': field(
        dtype=expected_map_dtype,
        # All the unique keys of the map got extracted as sub-fields in the Lilac schema.
        fields={'key1': ['int32'], 'key2': ['int32']},
      ),
      'id': 'int32',
    }
  )
  df = dataset.to_pandas()
  # Sort rows by id so that the test is deterministic.
  rows = sorted([row.to_dict() for _, row in df.iterrows()], key=lambda x: x['id'])
  expected_rows = [
    {'id': 0, 'name': {'key': ['key1'], 'value': [[1, 2, 3]]}},
    {'id': 1, 'name': {'key': ['key2'], 'value': [[2, 3]]}},
    {'id': 2, 'name': {'key': ['key1', 'key2'], 'value': [[3, 4], [5, 6]]}},
  ]
  assert rows == expected_rows
