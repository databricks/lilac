"""Tests for dataset.stats()."""

from datetime import datetime
from typing import Any, cast

import pytest
from pytest_mock import MockerFixture

from ..schema import Field, Item, MapType, schema
from . import dataset as dataset_module
from .dataset import StatsResult
from .dataset_test_utils import TestDataMaker

SIMPLE_ITEMS: list[Item] = [
  {'str': 'a', 'int': 1, 'bool': False, 'float': 3.0},
  {'str': 'b', 'int': 2, 'bool': True, 'float': 2.0},
  {'str': 'b', 'int': 2, 'bool': True, 'float': 1.0},
  {'float': float('nan')},
]


def test_simple_stats(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data(SIMPLE_ITEMS)

  result = dataset.stats(leaf_path='str')
  assert result == StatsResult(
    path=('str',), total_count=3, approx_count_distinct=2, avg_text_length=1
  )

  result = dataset.stats(leaf_path='float')
  assert result == StatsResult(
    path=('float',), total_count=4, approx_count_distinct=4, min_val=1.0, max_val=3.0
  )

  result = dataset.stats(leaf_path='bool')
  assert result == StatsResult(path=('bool',), total_count=3, approx_count_distinct=2)

  result = dataset.stats(leaf_path='int')
  assert result == StatsResult(
    path=('int',), total_count=3, approx_count_distinct=2, min_val=1, max_val=2
  )


def test_nested_stats(make_test_data: TestDataMaker) -> None:
  nested_items: list[Item] = [
    {'name': 'Name1', 'addresses': [{'zips': [5, 8]}]},
    {'name': 'Name2', 'addresses': [{'zips': [3]}, {'zips': [11, 8]}]},
    {'name': 'Name2', 'addresses': []},  # No addresses.
    {'name': 'Name2', 'addresses': [{'zips': []}]},  # No zips in the first address.
  ]
  nested_schema = schema({'name': 'string', 'addresses': [{'zips': ['int32']}]})
  dataset = make_test_data(nested_items, schema=nested_schema)

  result = dataset.stats(leaf_path='name')
  assert result == StatsResult(
    path=('name',), total_count=4, approx_count_distinct=2, avg_text_length=5
  )

  result = dataset.stats(leaf_path='addresses.*.zips.*')
  assert result == StatsResult(
    path=('addresses', '*', 'zips', '*'),
    total_count=5,
    approx_count_distinct=4,
    min_val=3,
    max_val=11,
  )


def test_stats_approximation(make_test_data: TestDataMaker, mocker: MockerFixture) -> None:
  sample_size = 5
  mocker.patch(f'{dataset_module.__name__}.TOO_MANY_DISTINCT', sample_size)

  nested_items: list[Item] = [{'feature': str(i)} for i in range(sample_size * 10)]
  nested_schema = schema({'feature': 'string'})
  dataset = make_test_data(nested_items, schema=nested_schema)

  result = dataset.stats(leaf_path='feature')
  assert result == StatsResult(
    path=('feature',), total_count=50, approx_count_distinct=50, avg_text_length=1
  )


def test_error_handling(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data(SIMPLE_ITEMS)

  with pytest.raises(ValueError, match='leaf_path must be provided'):
    dataset.stats(cast(Any, None))

  with pytest.raises(ValueError, match="Path \\('unknown',\\) not found in schema"):
    dataset.stats(leaf_path='unknown')


def test_map_dtype(make_test_data: TestDataMaker) -> None:
  items = [
    {'column': {'a': 1.0, 'b': 2.0}},
    {'column': {'b': 2.5}},
    {'column': {'a': 3.0, 'c': 3.5}},
  ]
  data_schema = schema({'column': Field(dtype=MapType(key_type='string', value_type='float32'))})
  dataset = make_test_data(items, schema=data_schema)
  assert dataset.stats('column.a') == StatsResult(
    path=('column', 'a'), total_count=2, approx_count_distinct=2, min_val=1.0, max_val=3.0
  )
  assert dataset.stats('column.b') == StatsResult(
    path=('column', 'b'), total_count=2, approx_count_distinct=2, min_val=2.0, max_val=2.5
  )
  assert dataset.stats('column.c') == StatsResult(
    path=('column', 'c'), total_count=1, approx_count_distinct=1, min_val=3.5, max_val=3.5
  )
  with pytest.raises(ValueError, match='Cannot compute stats on a map field'):
    dataset.stats('column')


def test_datetime(make_test_data: TestDataMaker) -> None:
  items: list[Item] = [
    {'id': '1', 'date': datetime(2023, 1, 1)},
    {'id': '2', 'date': datetime(2023, 1, 15)},
    {'id': '2', 'date': datetime(2023, 2, 1)},
    {'id': '4', 'date': datetime(2023, 3, 1)},
    {
      'id': '5'
      # Missing datetime.
    },
  ]
  dataset = make_test_data(items)
  result = dataset.stats('date')
  assert result == StatsResult(
    path=('date',),
    total_count=4,
    approx_count_distinct=4,
    min_val=datetime(2023, 1, 1),
    max_val=datetime(2023, 3, 1),
  )
