"""Tests for db.stats()."""

import pathlib
from typing import Any, Generator, Type, cast

import pytest
from pytest_mock import MockerFixture

from ..config import CONFIG
from ..schema import UUID_COLUMN, Item, schema
from . import db_dataset_duckdb
from .db_dataset import DatasetDB, StatsResult
from .db_dataset_duckdb import DatasetDuckDB
from .db_dataset_test_utils import make_db

ALL_DBS = [DatasetDuckDB]

SIMPLE_ITEMS: list[Item] = [{
  UUID_COLUMN: '1',
  'str': 'a',
  'int': 1,
  'bool': False,
  'float': 3.0
}, {
  UUID_COLUMN: '2',
  'str': 'b',
  'int': 2,
  'bool': True,
  'float': 2.0
}, {
  UUID_COLUMN: '3',
  'str': 'b',
  'int': 2,
  'bool': True,
  'float': 1.0
}]


@pytest.fixture(autouse=True)
def set_data_path(tmp_path: pathlib.Path) -> Generator:
  data_path = CONFIG['LILAC_DATA_PATH']
  CONFIG['LILAC_DATA_PATH'] = str(tmp_path)
  yield
  CONFIG['LILAC_DATA_PATH'] = data_path or ''


@pytest.mark.parametrize('db_cls', ALL_DBS)
class StatsSuite:

  def test_simple_stats(self, tmp_path: pathlib.Path, db_cls: Type[DatasetDB]) -> None:
    db = make_db(db_cls, tmp_path, SIMPLE_ITEMS)

    result = db.stats(leaf_path='str')
    assert result == StatsResult(total_count=3, approx_count_distinct=2, avg_text_length=1)

    result = db.stats(leaf_path='float')
    assert result == StatsResult(total_count=3, approx_count_distinct=3, min_val=1.0, max_val=3.0)

    result = db.stats(leaf_path='bool')
    assert result == StatsResult(total_count=3, approx_count_distinct=2)

    result = db.stats(leaf_path='int')
    assert result == StatsResult(total_count=3, approx_count_distinct=2, min_val=1, max_val=2)

  def test_nested_stats(self, tmp_path: pathlib.Path, db_cls: Type[DatasetDB]) -> None:
    nested_items: list[Item] = [
      {
        'name': 'Name1',
        'addresses': [{
          'zips': [5, 8]
        }]
      },
      {
        'name': 'Name2',
        'addresses': [{
          'zips': [3]
        }, {
          'zips': [11, 8]
        }]
      },
      {
        'name': 'Name2',
        'addresses': []
      },  # No addresses.
      {
        'name': 'Name2',
        'addresses': [{
          'zips': []
        }]
      }  # No zips in the first address.
    ]
    nested_schema = schema({
      UUID_COLUMN: 'string',
      'name': 'string',
      'addresses': [{
        'zips': ['int32']
      }]
    })
    db = make_db(db_cls=db_cls, tmp_path=tmp_path, items=nested_items, schema=nested_schema)

    result = db.stats(leaf_path='name')
    assert result == StatsResult(total_count=4, approx_count_distinct=2, avg_text_length=5)

    result = db.stats(leaf_path='addresses.*.zips.*')
    assert result == StatsResult(total_count=5, approx_count_distinct=4, min_val=3, max_val=11)

  def test_stats_approximation(self, tmp_path: pathlib.Path, db_cls: Type[DatasetDB],
                               mocker: MockerFixture) -> None:
    sample_size = 5
    mocker.patch(f'{db_dataset_duckdb.__name__}.SAMPLE_SIZE_DISTINCT_COUNT', sample_size)

    nested_items: list[Item] = [{'feature': str(i)} for i in range(sample_size * 10)]
    nested_schema = schema({UUID_COLUMN: 'string', 'feature': 'string'})
    db = make_db(db_cls=db_cls, tmp_path=tmp_path, items=nested_items, schema=nested_schema)

    result = db.stats(leaf_path='feature')
    assert result == StatsResult(total_count=50, approx_count_distinct=50, avg_text_length=1)

  def test_error_handling(self, tmp_path: pathlib.Path, db_cls: Type[DatasetDB]) -> None:
    db = make_db(db_cls=db_cls, tmp_path=tmp_path, items=SIMPLE_ITEMS)

    with pytest.raises(ValueError, match='leaf_path must be provided'):
      db.stats(cast(Any, None))

    with pytest.raises(ValueError, match='Leaf "\\(\'unknown\',\\)" not found in dataset'):
      db.stats(leaf_path='unknown')
