"""Tests for `db.select_rows_schema()`."""

import pathlib
from typing import Generator, Iterable, Optional, Type

import pytest

from ..config import CONFIG
from ..schema import (
  LILAC_COLUMN,
  UUID_COLUMN,
  EnrichmentType,
  Field,
  Item,
  RichData,
  SignalOut,
  field,
  schema,
  signal_field,
)
from ..signals.signal import Signal
from .db_dataset import DatasetDB, SignalUDF
from .db_dataset_duckdb import DatasetDuckDB
from .db_dataset_test_utils import make_db

ALL_DBS = [DatasetDuckDB]

SIMPLE_DATASET_NAME = 'simple'

TEST_DATA: list[Item] = [{
  UUID_COLUMN: '1',
  'erased': False,
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
  'erased': True,
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


@pytest.fixture(autouse=True)
def set_data_path(tmp_path: pathlib.Path) -> Generator:
  data_path = CONFIG['LILAC_DATA_PATH']
  CONFIG['LILAC_DATA_PATH'] = str(tmp_path)
  yield
  CONFIG['LILAC_DATA_PATH'] = data_path or ''


class LengthSignal(Signal):
  name = 'length_signal'
  enrichment_type = EnrichmentType.TEXT

  def fields(self) -> Field:
    return field('int32')

  def compute(self, data: Iterable[RichData]) -> Iterable[Optional[SignalOut]]:
    for text_content in data:
      yield len(text_content)


@pytest.mark.parametrize('db_cls', ALL_DBS)
class SelectRowsSchemaSuite:

  def test_simple_schema(self, tmp_path: pathlib.Path, db_cls: Type[DatasetDB]) -> None:
    db = make_db(db_cls, tmp_path, TEST_DATA)
    result = db.select_rows_schema(combine_columns=True)
    assert result == schema({
      UUID_COLUMN: 'string',
      'erased': 'boolean',
      'people': [{
        'name': 'string',
        'zipcode': 'int32',
        'locations': [{
          'city': 'string',
          'state': 'string'
        }]
      }]
    })

  def test_subselection_with_combine_cols(self, tmp_path: pathlib.Path,
                                          db_cls: Type[DatasetDB]) -> None:
    db = make_db(db_cls, tmp_path, TEST_DATA)

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

  def test_udf_with_combine_cols(self, tmp_path: pathlib.Path, db_cls: Type[DatasetDB]) -> None:
    db = make_db(db_cls, tmp_path, TEST_DATA)

    result = db.select_rows_schema([('people', '*', 'locations', '*', 'city'),
                                    SignalUDF(LengthSignal(), ('people', '*', 'name'))],
                                   combine_columns=True)
    assert result == schema({
      UUID_COLUMN: 'string',
      'people': [{
        'locations': [{
          'city': 'string'
        }]
      }],
      LILAC_COLUMN: {
        'people': [{
          'name': {
            'length_signal': signal_field(dtype='int32')
          }
        }]
      }
    })
