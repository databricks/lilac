"""Tests for `db.select_rows_schema()`."""

from typing import Iterable, Optional, cast

import pytest

from ..schema import UUID_COLUMN, Field, Item, RichData, SignalOut, field, schema, signal_field
from ..signals.signal import TextSignal, clear_signal_registry, register_signal
from .dataset import Column
from .dataset_test_utils import TestDataMaker

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


@pytest.fixture(scope='module', autouse=True)
def setup_teardown() -> Iterable[None]:
  # Setup.
  register_signal(LengthSignal)
  register_signal(AddSpaceSignal)

  # Unit test runs.
  yield

  # Teardown.
  clear_signal_registry()


class LengthSignal(TextSignal):
  name = 'length_signal'

  def fields(self) -> Field:
    return field('int32')

  def compute(self, data: Iterable[RichData]) -> Iterable[Optional[SignalOut]]:
    for text_content in data:
      yield len(text_content)


class AddSpaceSignal(TextSignal):
  name = 'add_space_signal'

  def fields(self) -> Field:
    return field('string')

  def compute(self, data: Iterable[RichData]) -> Iterable[Optional[SignalOut]]:
    for text_content in data:
      yield cast(str, text_content) + ' '


def test_simple_schema(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data(TEST_DATA)
  result = dataset.select_rows_schema(combine_columns=True)
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


def test_subselection_with_combine_cols(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data(TEST_DATA)

  result = dataset.select_rows_schema([('people', '*', 'zipcode'),
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

  result = dataset.select_rows_schema([('people', '*', 'name'), ('people', '*', 'locations')],
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

  result = dataset.select_rows_schema([('people', '*')], combine_columns=True)
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


def test_udf_with_combine_cols(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data(TEST_DATA)

  length_signal = LengthSignal()
  result = dataset.select_rows_schema([('people', '*', 'locations', '*', 'city'),
                                       Column(('people', '*', 'name'), signal_udf=length_signal)],
                                      combine_columns=True)
  assert result == schema({
    UUID_COLUMN: 'string',
    'people': [{
      'name': {
        'length_signal': signal_field(dtype='int32', signal=length_signal.dict())
      },
      'locations': [{
        'city': 'string'
      }]
    }],
  })


def test_embedding_udf_with_combine_cols(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data(TEST_DATA)

  add_space_signal = AddSpaceSignal()
  dataset.compute_signal(add_space_signal, ('people', '*', 'name'))
  result = dataset.select_rows_schema(
    [('people', '*', 'name'),
     Column(('people', '*', 'name', 'add_space_signal'), signal_udf=add_space_signal)],
    combine_columns=True)
  assert result == schema({
    UUID_COLUMN: 'string',
    'people': [{
      'name': field(
        {
          'add_space_signal': signal_field(
            fields={
              'add_space_signal': signal_field(dtype='string', signal=add_space_signal.dict()),
            },
            dtype='string',
            signal=add_space_signal.dict())
        },
        dtype='string')
    }],
  })
