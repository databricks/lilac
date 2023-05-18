"""Tests for dataset.select_rows(filters=[...])."""

import pytest

from ..schema import UUID_COLUMN, Item, schema
from .dataset import BinaryFilterTuple, BinaryOp, ListFilterTuple, ListOp, UnaryOp
from .dataset_test_utils import TestDataMaker
from .dataset_utils import lilac_items

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
}]


def test_filter_by_ids(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data(TEST_DATA)

  id_filter: BinaryFilterTuple = (UUID_COLUMN, BinaryOp.EQUALS, '1')
  result = dataset.select_rows(filters=[id_filter])

  assert list(result) == lilac_items([{
    UUID_COLUMN: '1',
    'str': 'a',
    'int': 1,
    'bool': False,
    'float': 3.0
  }])

  id_filter = (UUID_COLUMN, BinaryOp.EQUALS, '2')
  result = dataset.select_rows(filters=[id_filter])

  assert list(result) == lilac_items([{
    UUID_COLUMN: '2',
    'str': 'b',
    'int': 2,
    'bool': True,
    'float': 2.0
  }])

  id_filter = (UUID_COLUMN, BinaryOp.EQUALS, b'f')
  result = dataset.select_rows(filters=[id_filter])

  assert list(result) == []


def test_filter_by_list_of_ids(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data(TEST_DATA)

  id_filter: ListFilterTuple = (UUID_COLUMN, ListOp.IN, ['1', '2'])
  result = dataset.select_rows(filters=[id_filter])

  assert list(result) == lilac_items([{
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
  }])


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
  assert list(result) == lilac_items([{
    UUID_COLUMN: '1',
    'name': 'A'
  }, {
    UUID_COLUMN: '3',
    'name': 'C'
  }])

  exists_filter = ('info.lang', UnaryOp.EXISTS)
  result = dataset.select_rows(['name'], filters=[exists_filter])
  assert list(result) == lilac_items([{
    UUID_COLUMN: '1',
    'name': 'A'
  }, {
    UUID_COLUMN: '2',
    'name': None
  }])

  exists_filter = ('ages.*.*', UnaryOp.EXISTS)
  result = dataset.select_rows(['name'], filters=[exists_filter])
  assert list(result) == lilac_items([{UUID_COLUMN: '3', 'name': 'C'}])

  with pytest.raises(ValueError, match='Unable to filter on path'):
    dataset.select_rows(['name'], filters=[('info', UnaryOp.EXISTS)])
