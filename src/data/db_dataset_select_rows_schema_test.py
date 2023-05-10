"""Tests for `db.select_rows_schema()`."""

import pathlib
from typing import Generator, Type

import pytest

from ..config import CONFIG
from ..schema import UUID_COLUMN, Item, schema
from .db_dataset import DatasetDB
from .db_dataset_duckdb import DatasetDuckDB
from .db_dataset_test_utils import make_db

ALL_DBS = [DatasetDuckDB]

SIMPLE_DATASET_NAME = 'simple'

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
class SelectRowsSchemaSuite:

  def test_simple_schema(self, tmp_path: pathlib.Path, db_cls: Type[DatasetDB]) -> None:
    db = make_db(db_cls, tmp_path, SIMPLE_ITEMS)
    result = db.select_rows_schema(combine_columns=True)
    assert result == schema({
      UUID_COLUMN: 'string',
      'str': 'string',
      'int': 'int32',
      'bool': 'boolean',
      'float': 'float32'
    })

  def test_subselection_with_combine_cols(self, tmp_path: pathlib.Path,
                                          db_cls: Type[DatasetDB]) -> None:
    items: list[Item] = [{
      UUID_COLUMN: '1',
      'people': [{
        'name': 'A',
        'zipcode': 0,
        'locations': [{
          'city': 'city1',
          'state': 'state1'
        }, {
          'city': 'city2',
          'state': 'state2'
        }]
      }]
    }, {
      UUID_COLUMN: '2',
      'people': [{
        'name': 'B',
        'zipcode': 1,
        'locations': [{
          'city': 'city3',
          'state': 'state3'
        }, {
          'city': 'city4'
        }, {
          'city': 'city5'
        }]
      }, {
        'name': 'C',
        'zipcode': 2,
        'locations': [{
          'city': 'city1',
          'state': 'state1'
        }]
      }]
    }]
    db = make_db(db_cls, tmp_path, items)

    result = db.select_rows_schema([('people', '*', 'zipcode'),
                                    ('people', '*', 'locations', '*', 'city')],
                                   combine_columns=True)
    assert result == schema({
      UUID_COLUMN: 'string',
      'people': [{
        'zipcode': 'int32',
        'locations': [{
          'city': 'string'
        }]
      }]
    })

    result = db.select_rows_schema([('people', '*', 'name'), ('people', '*', 'locations')],
                                   combine_columns=True)
    assert result == schema({
      UUID_COLUMN: 'string',
      'people': [{
        'name': 'string',
        'locations': [{
          'city': 'string',
          'state': 'string'
        }]
      }]
    })

    result = db.select_rows_schema([('people', '*')], combine_columns=True)
    assert result == schema({
      UUID_COLUMN: 'string',
      'people': [{
        'name': 'string',
        'zipcode': 'int32',
        'locations': [{
          'city': 'string',
          'state': 'string'
        }]
      }]
    })
