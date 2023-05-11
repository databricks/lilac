"""Tests for `db.select_rows_schema()`."""

import pathlib
from typing import Generator, Iterable, Optional, Type, cast

import pytest

from ..config import CONFIG
from ..schema import (
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
from ..signals.signal_registry import clear_signal_registry, register_signal
from .db_dataset import DatasetDB, SignalUDF
from .db_dataset_duckdb import DatasetDuckDB
from .db_dataset_test_utils import make_db

ALL_DBS = [DatasetDuckDB]

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


@pytest.fixture(scope='module', autouse=True)
def setup_teardown() -> Iterable[None]:
  # Setup.
  register_signal(LengthSignal)
  register_signal(AddSpaceSignal)

  # Unit test runs.
  yield

  # Teardown.
  clear_signal_registry()


class LengthSignal(Signal):
  name = 'length_signal'
  enrichment_type = EnrichmentType.TEXT

  def fields(self) -> Field:
    return field('int32')

  def compute(self, data: Iterable[RichData]) -> Iterable[Optional[SignalOut]]:
    for text_content in data:
      yield len(text_content)


class AddSpaceSignal(Signal):
  name = 'add_space_signal'
  enrichment_type = EnrichmentType.TEXT

  def fields(self) -> Field:
    return field('string')

  def compute(self, data: Iterable[RichData]) -> Iterable[Optional[SignalOut]]:
    for text_content in data:
      yield cast(str, text_content) + ' '


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
        'name': {
          'length_signal': signal_field(dtype='int32')
        },
        'locations': [{
          'city': 'string'
        }]
      }],
    })

  def test_embedding_udf_with_combine_cols(self, tmp_path: pathlib.Path,
                                           db_cls: Type[DatasetDB]) -> None:
    db = make_db(db_cls, tmp_path, TEST_DATA)

    db.compute_signal(AddSpaceSignal(), ('people', '*', 'name'))
    result = db.select_rows_schema([('people', '*', 'name'),
                                    SignalUDF(AddSpaceSignal(),
                                              ('people', '*', 'name', 'add_space_signal'))],
                                   combine_columns=True)
    assert result == schema({
      UUID_COLUMN: 'string',
      'people': [{
        'name': field(
          {
            'add_space_signal': signal_field({
              'add_space_signal': signal_field(dtype='string'),
            },
                                             dtype='string')
          },
          dtype='string')
      }],
    })
