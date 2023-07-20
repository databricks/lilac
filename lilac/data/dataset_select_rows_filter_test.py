"""Tests for dataset.select_rows(filters=[...])."""

import pytest

from ..schema import UUID_COLUMN, Item, schema
from .dataset import BinaryFilterTuple, BinaryOp, ListFilterTuple, ListOp, UnaryOp
from .dataset_test_utils import TestDataMaker

TEST_DATA: list[Item] = [{
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
}, {
  UUID_COLUMN: '4',
  'float': float('nan')
}]


def test_filter_by_ids(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data(TEST_DATA)

  id_filter: BinaryFilterTuple = (UUID_COLUMN, BinaryOp.EQUALS, '1')
  result = dataset.select_rows(filters=[id_filter])

  assert list(result) == [{UUID_COLUMN: '1', 'str': 'a', 'int': 1, 'bool': False, 'float': 3.0}]

  id_filter = (UUID_COLUMN, BinaryOp.EQUALS, '2')
  result = dataset.select_rows(filters=[id_filter])

  assert list(result) == [{UUID_COLUMN: '2', 'str': 'b', 'int': 2, 'bool': True, 'float': 2.0}]

  id_filter = (UUID_COLUMN, BinaryOp.EQUALS, b'f')
  result = dataset.select_rows(filters=[id_filter])

  assert list(result) == []


def test_filter_greater(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data(TEST_DATA)

  id_filter: BinaryFilterTuple = ('float', BinaryOp.GREATER, 2.0)
  result = dataset.select_rows(filters=[id_filter])

  assert list(result) == [{UUID_COLUMN: '1', 'str': 'a', 'int': 1, 'bool': False, 'float': 3.0}]


def test_filter_greater_equal(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data(TEST_DATA)

  id_filter: BinaryFilterTuple = ('float', BinaryOp.GREATER_EQUAL, 2.0)
  result = dataset.select_rows(filters=[id_filter])

  assert list(result) == [{
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
  }]


def test_filter_less(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data(TEST_DATA)

  id_filter: BinaryFilterTuple = ('float', BinaryOp.LESS, 2.0)
  result = dataset.select_rows(filters=[id_filter])

  assert list(result) == [{UUID_COLUMN: '3', 'str': 'b', 'int': 2, 'bool': True, 'float': 1.0}]


def test_filter_less_equal(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data(TEST_DATA)

  id_filter: BinaryFilterTuple = ('float', BinaryOp.LESS_EQUAL, 2.0)
  result = dataset.select_rows(filters=[id_filter])

  assert list(result) == [{
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


def test_filter_not_equal(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data(TEST_DATA)

  id_filter: BinaryFilterTuple = ('float', BinaryOp.NOT_EQUAL, 2.0)
  result = dataset.select_rows(filters=[id_filter])

  assert list(result) == [
    {
      UUID_COLUMN: '1',
      'str': 'a',
      'int': 1,
      'bool': False,
      'float': 3.0
    },
    {
      UUID_COLUMN: '3',
      'str': 'b',
      'int': 2,
      'bool': True,
      'float': 1.0
    },
    # NaNs are not counted when we are filtering a field.
  ]


def test_filter_by_list_of_ids(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data(TEST_DATA)

  id_filter: ListFilterTuple = (UUID_COLUMN, ListOp.IN, ['1', '2'])
  result = dataset.select_rows(filters=[id_filter])

  assert list(result) == [{
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
  }]


def test_filter_by_exists(make_test_data: TestDataMaker) -> None:
  items: list[Item] = [{
    UUID_COLUMN: '1',
    'name': 'A',
    'info': {
      'lang': 'en'
    },
    'ages': []
  }, {
    UUID_COLUMN: '2',
    'info': {
      'lang': 'fr'
    },
  }, {
    UUID_COLUMN: '3',
    'name': 'C',
    'ages': [[1, 2], [3, 4]]
  }]
  dataset = make_test_data(
    items,
    schema=schema({
      UUID_COLUMN: 'string',
      'name': 'string',
      'info': {
        'lang': 'string'
      },
      'ages': [['int32']]
    }))

  exists_filter = ('name', UnaryOp.EXISTS)
  result = dataset.select_rows(['name'], filters=[exists_filter])
  assert list(result) == [{UUID_COLUMN: '1', 'name': 'A'}, {UUID_COLUMN: '3', 'name': 'C'}]

  exists_filter = ('info.lang', UnaryOp.EXISTS)
  result = dataset.select_rows(['name'], filters=[exists_filter])
  assert list(result) == [{UUID_COLUMN: '1', 'name': 'A'}, {UUID_COLUMN: '2', 'name': None}]

  exists_filter = ('ages.*.*', UnaryOp.EXISTS)
  result = dataset.select_rows(['name'], filters=[exists_filter])
  assert list(result) == [{UUID_COLUMN: '3', 'name': 'C'}]

  with pytest.raises(ValueError, match='Unable to filter on path'):
    dataset.select_rows(['name'], filters=[('info', UnaryOp.EXISTS)])
