"""Tests for dataset.select_groups()."""

import re
from datetime import datetime

import pytest
from pytest_mock import MockerFixture

from ..schema import Field, Item, MapType, field, schema
from . import dataset as dataset_module
from .dataset import GroupsSortBy, SelectGroupsResult, SortOrder
from .dataset_test_utils import TestDataMaker


def test_flat_data(make_test_data: TestDataMaker) -> None:
  items: list[Item] = [
    {'name': 'Name1', 'age': 34, 'active': False},
    {'name': 'Name2', 'age': 45, 'active': True},
    {'age': 17, 'active': True},  # Missing "name".
    {'name': 'Name3', 'active': True},  # Missing "age".
    {'name': 'Name4', 'age': 55},  # Missing "active".
  ]
  dataset = make_test_data(items)

  result = dataset.select_groups(leaf_path='name')

  assert result.counts == [('Name1', 1), ('Name2', 1), ('Name3', 1), ('Name4', 1), (None, 1)]

  result = dataset.select_groups(leaf_path='age', bins=[20, 50, 60])
  assert result.counts == [('1', 2), ('0', 1), ('2', 1), (None, 1)]

  result = dataset.select_groups(leaf_path='active')
  assert result.counts == [
    (True, 3),
    (False, 1),
    (None, 1),  # Missing "active".
  ]


def test_result_counts(make_test_data: TestDataMaker) -> None:
  items: list[Item] = [
    {'active': False},
    {'active': True},
    {'active': True},
    {'active': True},
    {},  # Missing "active".
  ]
  dataset = make_test_data(items, schema=schema({'active': 'boolean'}))

  result = dataset.select_groups(leaf_path='active')
  assert result.counts == [(True, 3), (False, 1), (None, 1)]


def test_order_by_value(make_test_data: TestDataMaker) -> None:
  items: list[Item] = [
    {'active': False},
    {'active': False},
    {'active': True},
    {'active': False},
    {},  # Missing "active".
  ]
  dataset = make_test_data(items, schema=schema({'active': 'boolean'}))

  result = dataset.select_groups(leaf_path='active', sort_by=GroupsSortBy.VALUE)
  assert result.counts == [(True, 1), (False, 3), (None, 1)]

  result = dataset.select_groups(
    leaf_path='active', sort_by=GroupsSortBy.VALUE, sort_order=SortOrder.ASC
  )
  assert result.counts == [(False, 3), (True, 1), (None, 1)]


def test_list_of_structs(make_test_data: TestDataMaker) -> None:
  items: list[Item] = [
    {'list_of_structs': [{'name': 'a'}, {'name': 'b'}]},
    {'list_of_structs': [{'name': 'c'}, {'name': 'a'}, {'name': 'd'}]},
    {'list_of_structs': [{'name': 'd'}]},
  ]
  dataset = make_test_data(items)

  result = dataset.select_groups(leaf_path='list_of_structs.*.name')
  assert result.counts == [('a', 2), ('d', 2), ('b', 1), ('c', 1)]


def test_nested_lists(make_test_data: TestDataMaker) -> None:
  items: list[Item] = [
    {'nested_list': [[{'name': 'a'}], [{'name': 'b'}]]},
    {'nested_list': [[{'name': 'c'}, {'name': 'a'}], [{'name': 'd'}]]},
    {'nested_list': [[{'name': 'd'}]]},
  ]
  dataset = make_test_data(items)

  result = dataset.select_groups(leaf_path='nested_list.*.*.name')
  assert result.counts == [('a', 2), ('d', 2), ('b', 1), ('c', 1)]


def test_nested_struct(make_test_data: TestDataMaker) -> None:
  items: list[Item] = [
    {'nested_struct': {'struct': {'name': 'c'}}},
    {'nested_struct': {'struct': {'name': 'b'}}},
    {'nested_struct': {'struct': {'name': 'a'}}},
  ]
  dataset = make_test_data(items)

  result = dataset.select_groups(leaf_path='nested_struct.struct.name')
  assert result.counts == [('a', 1), ('b', 1), ('c', 1)]


def test_named_bins(make_test_data: TestDataMaker) -> None:
  items: list[Item] = [
    {'age': 34.0},
    {'age': 45.0},
    {'age': 17.0},
    {'age': 80.0},
    {'age': 55.0},
    {'age': float('nan')},
  ]
  dataset = make_test_data(items)

  result = dataset.select_groups(
    leaf_path='age',
    bins=[('young', None, 20), ('adult', 20, 50), ('middle-aged', 50, 65), ('senior', 65, None)],
  )
  assert result.counts == [('adult', 2), ('middle-aged', 1), ('senior', 1), ('young', 1), (None, 1)]


def test_schema_with_bins(make_test_data: TestDataMaker) -> None:
  items: list[Item] = [
    {'age': 34},
    {'age': 45},
    {'age': 17},
    {'age': 80},
    {'age': 55},
    {'age': float('nan')},
  ]
  data_schema = schema(
    {
      'age': field(
        'float32',
        bins=[
          ('young', None, 20),
          ('adult', 20, 50),
          ('middle-aged', 50, 65),
          ('senior', 65, None),
        ],
      )
    }
  )
  dataset = make_test_data(items, data_schema)

  result = dataset.select_groups(leaf_path='age')
  assert result.counts == [('adult', 2), ('middle-aged', 1), ('senior', 1), ('young', 1), (None, 1)]


def test_filters(make_test_data: TestDataMaker) -> None:
  items: list[Item] = [
    {'name': 'Name1', 'age': 34, 'active': False},
    {'name': 'Name2', 'age': 45, 'active': True},
    {'age': 17, 'active': True},  # Missing "name".
    {'name': 'Name3', 'active': True},  # Missing "age".
    {'name': 'Name4', 'age': 55},  # Missing "active".
  ]
  dataset = make_test_data(items)

  # active = True.
  result = dataset.select_groups(leaf_path='name', filters=[('active', 'equals', True)])
  assert result.counts == [('Name2', 1), ('Name3', 1), (None, 1)]

  # age < 35.
  result = dataset.select_groups(leaf_path='name', filters=[('age', 'less', 35)])
  assert result.counts == [('Name1', 1), (None, 1)]

  # age < 35 and active = True.
  result = dataset.select_groups(
    leaf_path='name', filters=[('age', 'less', 35), ('active', 'equals', True)]
  )
  assert result.counts == [(None, 1)]


def test_datetime(make_test_data: TestDataMaker) -> None:
  items: list[Item] = [
    {'id': 1, 'date': datetime(2023, 1, 1)},
    {'id': 2, 'date': datetime(2023, 1, 15)},
    {'id': 3, 'date': datetime(2023, 2, 1)},
    {'id': 4, 'date': datetime(2023, 3, 1)},
    {
      'id': 5
      # Missing datetime.
    },
  ]
  dataset = make_test_data(items)
  result = dataset.select_groups('date')
  assert result.counts == [
    (datetime(2023, 1, 1), 1),
    (datetime(2023, 1, 15), 1),
    (datetime(2023, 2, 1), 1),
    (datetime(2023, 3, 1), 1),
    (None, 1),
  ]


def test_invalid_leaf(make_test_data: TestDataMaker) -> None:
  items: list[Item] = [
    {'nested_struct': {'struct': {'name': 'c'}}},
    {'nested_struct': {'struct': {'name': 'b'}}},
    {'nested_struct': {'struct': {'name': 'a'}}},
  ]
  dataset = make_test_data(items)

  with pytest.raises(
    ValueError, match=re.escape('Leaf "(\'nested_struct\',)" not found in dataset')
  ):
    dataset.select_groups(leaf_path='nested_struct')

  with pytest.raises(
    ValueError, match=re.escape("Leaf \"('nested_struct', 'struct')\" not found in dataset")
  ):
    dataset.select_groups(leaf_path='nested_struct.struct')

  with pytest.raises(
    ValueError,
    match=re.escape("Path ('nested_struct', 'struct', 'wrong_name') not found in schema"),
  ):
    dataset.select_groups(leaf_path='nested_struct.struct.wrong_name')


def test_too_many_distinct(make_test_data: TestDataMaker, mocker: MockerFixture) -> None:
  too_many_distinct = 5
  mocker.patch(f'{dataset_module.__name__}.TOO_MANY_DISTINCT', too_many_distinct)

  items: list[Item] = [{'feature': str(i)} for i in range(too_many_distinct + 10)]
  dataset = make_test_data(items)

  res = dataset.select_groups('feature')
  assert res.too_many_distinct is True
  assert res.counts == []


def test_auto_bins_for_float(make_test_data: TestDataMaker) -> None:
  items: list[Item] = [{'feature': float(i)} for i in range(5)] + [{'feature': float('nan')}]
  dataset = make_test_data(items)

  res = dataset.select_groups('feature')
  assert res.counts == [('0', 1), ('11', 1), ('14', 1), ('3', 1), ('7', 1), (None, 1)]
  assert res.too_many_distinct is False
  assert res.bins


def test_map_dtype(make_test_data: TestDataMaker) -> None:
  items = [
    {'column': {'a': 1.0, 'b': 2.0}},
    {'column': {'b': 2.5}},
    {'column': {'a': 3.0, 'c': 3.5}},
  ]
  data_schema = schema({'column': Field(dtype=MapType(key_type='string', value_type='float32'))})
  dataset = make_test_data(items, schema=data_schema)
  assert dataset.select_groups('column.a', bins=[0, 2]) == SelectGroupsResult(
    too_many_distinct=False,
    counts=[('1', 1), ('2', 1)],
    bins=[('0', None, 0), ('1', 0, 2), ('2', 2, None)],
  )
  assert dataset.select_groups('column.b', bins=[0, 1.5]) == SelectGroupsResult(
    too_many_distinct=False,
    counts=[('2', 2)],
    bins=[('0', None, 0), ('1', 0, 1.5), ('2', 1.5, None)],
  )
  assert dataset.select_groups('column.c', bins=[0, 2]) == SelectGroupsResult(
    too_many_distinct=False,
    counts=[('2', 1)],
    bins=[('0', None, 0), ('1', 0, 2), ('2', 2, None)],
  )
  with pytest.raises(ValueError, match='Cannot compute groups on a map field'):
    dataset.select_groups('column')
