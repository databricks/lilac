"""Tests for dataset.select_rows(filters=[...])."""

import pytest

from ..schema import ROWID, Item, schema
from .dataset import BinaryFilterTuple, ListFilterTuple, UnaryFilterTuple
from .dataset_test_utils import TestDataMaker

TEST_DATA: list[Item] = [{
  'str': 'a',
  'int': 1,
  'bool': False,
  'float': 3.0
}, {
  'str': 'b',
  'int': 2,
  'bool': True,
  'float': 2.0
}, {
  'str': 'b',
  'int': 2,
  'bool': True,
  'float': 1.0
}, {
  'float': float('nan')
}]


def test_filter_by_ids(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data(TEST_DATA)

  id_filter: BinaryFilterTuple = (ROWID, 'equals', '1')
  result = dataset.select_rows(filters=[id_filter])

  assert list(result) == [{'str': 'a', 'int': 1, 'bool': False, 'float': 3.0}]

  id_filter = (ROWID, 'equals', '2')
  result = dataset.select_rows(filters=[id_filter])

  assert list(result) == [{'str': 'b', 'int': 2, 'bool': True, 'float': 2.0}]

  id_filter = (ROWID, 'equals', b'f')
  result = dataset.select_rows(filters=[id_filter])

  assert list(result) == []


def test_filter_greater(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data(TEST_DATA)

  filter: BinaryFilterTuple = ('float', 'greater', 2.0)
  result = dataset.select_rows(filters=[filter])

  assert list(result) == [{'str': 'a', 'int': 1, 'bool': False, 'float': 3.0}]


def test_filter_greater_equal(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data(TEST_DATA)

  filter: BinaryFilterTuple = ('float', 'greater_equal', 2.0)
  result = dataset.select_rows(filters=[filter])

  assert list(result) == [{
    'str': 'a',
    'int': 1,
    'bool': False,
    'float': 3.0
  }, {
    'str': 'b',
    'int': 2,
    'bool': True,
    'float': 2.0
  }]


def test_filter_less(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data(TEST_DATA)

  filter: BinaryFilterTuple = ('float', 'less', 2.0)
  result = dataset.select_rows([ROWID, '*'], filters=[filter])

  assert list(result) == [{ROWID: '3', 'str': 'b', 'int': 2, 'bool': True, 'float': 1.0}]


def test_filter_less_equal(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data(TEST_DATA)

  filter: BinaryFilterTuple = ('float', 'less_equal', 2.0)
  result = dataset.select_rows(filters=[filter])

  assert list(result) == [{
    'str': 'b',
    'int': 2,
    'bool': True,
    'float': 2.0
  }, {
    'str': 'b',
    'int': 2,
    'bool': True,
    'float': 1.0
  }]


def test_filter_not_equal(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data(TEST_DATA)

  filter: BinaryFilterTuple = ('float', 'not_equal', 2.0)
  result = dataset.select_rows(filters=[filter])

  assert list(result) == [
    {
      'str': 'a',
      'int': 1,
      'bool': False,
      'float': 3.0
    },
    {
      'str': 'b',
      'int': 2,
      'bool': True,
      'float': 1.0
    },
    # NaNs are not counted when we are filtering a field.
  ]


def test_filter_by_list_of_ids(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data(TEST_DATA)

  filter: ListFilterTuple = (ROWID, 'in', ['1', '2'])
  result = dataset.select_rows(['*', ROWID], filters=[filter])

  assert list(result) == [{
    ROWID: '1',
    'str': 'a',
    'int': 1,
    'bool': False,
    'float': 3.0
  }, {
    ROWID: '2',
    'str': 'b',
    'int': 2,
    'bool': True,
    'float': 2.0
  }]


def test_filter_by_exists(make_test_data: TestDataMaker) -> None:
  items: list[Item] = [{
    ROWID: '1',
    'name': 'A',
    'info': {
      'lang': 'en'
    },
    'ages': []
  }, {
    ROWID: '2',
    'info': {
      'lang': 'fr'
    },
  }, {
    ROWID: '3',
    'name': 'C',
    'ages': [[1, 2], [3, 4]]
  }]
  dataset = make_test_data(
    items,
    schema=schema({
      ROWID: 'string',
      'name': 'string',
      'info': {
        'lang': 'string'
      },
      'ages': [['int32']]
    }))

  exists_filter: UnaryFilterTuple = ('name', 'exists')
  result = dataset.select_rows([ROWID, 'name'], filters=[exists_filter])
  assert list(result) == [{ROWID: '1', 'name': 'A'}, {ROWID: '3', 'name': 'C'}]

  exists_filter = ('info.lang', 'exists')
  result = dataset.select_rows([ROWID, 'name'], filters=[exists_filter])
  assert list(result) == [{ROWID: '1', 'name': 'A'}, {ROWID: '2', 'name': None}]

  exists_filter = ('ages.*.*', 'exists')
  result = dataset.select_rows([ROWID, 'name'], filters=[exists_filter])
  assert list(result) == [{ROWID: '3', 'name': 'C'}]

  with pytest.raises(ValueError, match='Unable to filter on path'):
    dataset.select_rows(['name'], filters=[('info', 'exists')])
