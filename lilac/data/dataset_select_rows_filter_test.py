"""Tests for dataset.select_rows(filters=[...])."""

from typing import ClassVar, Iterable, Iterator, Optional

from ..schema import ROWID, Field, Item, MapType, RichData, field, schema
from ..signal import TextSignal
from .dataset import BinaryFilterTuple, ListFilterTuple, StringFilterTuple, UnaryFilterTuple
from .dataset_test_utils import TestDataMaker

TEST_DATA: list[Item] = [
  {'str': 'a', 'int': 1, 'bool': False, 'float': 3.0},
  {'str': 'b', 'int': 2, 'bool': True, 'float': 2.0},
  {'str': 'b', 'int': 2, 'bool': True, 'float': 1.0},
  {'float': float('nan')},
]


STRING_TEST_DATA: list[Item] = [
  {'str': 'abcde', 'int': 1},
  {'str': 'a' * 10, 'int': 2},
  {'str': '', 'int': 3},
]


def test_filter_by_ids(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data(TEST_DATA)

  id_filter: BinaryFilterTuple = (ROWID, 'equals', '00001')
  result = dataset.select_rows(filters=[id_filter])

  assert list(result) == [{'str': 'a', 'int': 1, 'bool': False, 'float': 3.0}]

  id_filter = (ROWID, 'equals', '00002')
  result = dataset.select_rows(filters=[id_filter])

  assert list(result) == [{'str': 'b', 'int': 2, 'bool': True, 'float': 2.0}]

  id_filter = (ROWID, 'equals', b'f')
  result = dataset.select_rows(filters=[id_filter])

  assert list(result) == []


def test_filter_deleted_interaction(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data(TEST_DATA)

  id_filter: BinaryFilterTuple = (ROWID, 'equals', '00001')
  result = dataset.select_rows(filters=[id_filter])

  assert list(result) == [{'str': 'a', 'int': 1, 'bool': False, 'float': 3.0}]

  dataset.delete_rows(filters=[id_filter])
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

  assert list(result) == [
    {'str': 'a', 'int': 1, 'bool': False, 'float': 3.0},
    {'str': 'b', 'int': 2, 'bool': True, 'float': 2.0},
  ]


def test_filter_less(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data(TEST_DATA)

  filter: BinaryFilterTuple = ('float', 'less', 2.0)
  result = dataset.select_rows(['*'], filters=[filter])

  assert list(result) == [{'str': 'b', 'int': 2, 'bool': True, 'float': 1.0}]


def test_filter_less_equal(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data(TEST_DATA)

  filter: BinaryFilterTuple = ('float', 'less_equal', 2.0)
  result = dataset.select_rows(filters=[filter])

  assert list(result) == [
    {'str': 'b', 'int': 2, 'bool': True, 'float': 2.0},
    {'str': 'b', 'int': 2, 'bool': True, 'float': 1.0},
  ]


def test_filter_not_equal(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data(TEST_DATA)

  filter: BinaryFilterTuple = ('float', 'not_equal', 2.0)
  result = dataset.select_rows(filters=[filter])

  assert list(result) == [
    {'str': 'a', 'int': 1, 'bool': False, 'float': 3.0},
    {'str': 'b', 'int': 2, 'bool': True, 'float': 1.0},
    # NaNs are not counted when we are filtering a field.
  ]


def test_filter_length_longer(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data(STRING_TEST_DATA)

  filter: StringFilterTuple = ('str', 'length_longer', 5)
  result = dataset.select_rows(filters=[filter])

  assert list(result) == [{'str': 'abcde', 'int': 1}, {'str': 'a' * 10, 'int': 2}]


def test_filter_length_shorter(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data(STRING_TEST_DATA)

  filter: StringFilterTuple = ('str', 'length_shorter', 5)
  result = dataset.select_rows(filters=[filter])

  assert list(result) == [{'str': 'abcde', 'int': 1}, {'str': '', 'int': 3}]


def test_filter_string_regex_matches(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data(STRING_TEST_DATA)

  filter: StringFilterTuple = ('str', 'regex_matches', 'a+')
  result = dataset.select_rows(filters=[filter])

  assert list(result) == [{'str': 'abcde', 'int': 1}, {'str': 'a' * 10, 'int': 2}]


def test_filter_string_regex_matches_escaped(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data(
    [
      {'str': '..', 'int': 1},
      {'str': 'abc', 'int': 2},
    ]
  )

  filter: StringFilterTuple = ('str', 'regex_matches', r'\.+')
  result = dataset.select_rows(filters=[filter])

  assert list(result) == [{'str': '..', 'int': 1}]


def test_filter_string_regex_matches_newlines(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data(
    [
      {'str': 'hello\nworld', 'int': 1},
      {'str': 'hello\nworld\n', 'int': 2},
    ]
  )

  filter: StringFilterTuple = ('str', 'regex_matches', r'world\n')
  result = dataset.select_rows(filters=[filter])

  assert list(result) == [{'str': 'hello\nworld\n', 'int': 2}]


def test_filter_string_not_regex_matches(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data(STRING_TEST_DATA)

  filter: StringFilterTuple = ('str', 'not_regex_matches', 'a+')
  result = dataset.select_rows(filters=[filter])

  assert list(result) == [{'str': '', 'int': 3}]


def test_filter_by_list_of_ids(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data(TEST_DATA)

  filter: ListFilterTuple = (ROWID, 'in', ['00001', '00002'])
  result = dataset.select_rows(['*', ROWID], filters=[filter])

  assert list(result) == [
    {ROWID: '00001', 'str': 'a', 'int': 1, 'bool': False, 'float': 3.0},
    {ROWID: '00002', 'str': 'b', 'int': 2, 'bool': True, 'float': 2.0},
  ]


def test_filter_by_exists(make_test_data: TestDataMaker) -> None:
  items: list[Item] = [
    {'name': 'A', 'info': {'lang': 'en'}, 'ages': []},
    {'info': {'lang': 'fr'}},
    {'name': 'C', 'ages': [[1, 2], [3, 4]]},
  ]
  dataset = make_test_data(items)

  exists_filter: UnaryFilterTuple = ('name', 'exists')
  result = dataset.select_rows(['name'], filters=[exists_filter])
  assert list(result) == [{'name': 'A'}, {'name': 'C'}]

  exists_filter = ('info.lang', 'exists')
  result = dataset.select_rows(['name'], filters=[exists_filter])
  assert list(result) == [{'name': 'A'}, {'name': None}]

  exists_filter = ('ages.*.*', 'exists')
  result = dataset.select_rows(['name'], filters=[exists_filter])
  assert list(result) == [{'name': 'C'}]

  result = dataset.select_rows(['name'], filters=[('info', 'exists')])
  assert list(result) == [{'name': 'A'}, {'name': None}]


def test_filter_by_exists_on_enriched(make_test_data: TestDataMaker) -> None:
  items: list[Item] = [
    {'name': 'A', 'info': {'lang': 'en'}, 'ages': []},
    {'info': {'lang': 'fr'}},
    {'name': 'C', 'ages': [[1, 2], [3, 4]]},
  ]
  dataset = make_test_data(items)

  class LengthSignal(TextSignal):
    name: ClassVar[str] = 'length_signal'

    def fields(self) -> Field:
      return field('int32')

    def compute(self, data: Iterable[RichData]) -> Iterator[Optional[Item]]:
      for text_content in data:
        yield len(text_content)

  dataset.compute_signal(LengthSignal(), path=('info', 'lang'))
  result = dataset.select_rows(['name'], filters=[('info', 'exists')])
  assert list(result) == [{'name': 'A'}, {'name': None}]


def test_filter_by_not_exists(make_test_data: TestDataMaker) -> None:
  items: list[Item] = [
    {'name': 'A', 'info': {'lang': 'en'}, 'ages': []},
    {'info': {'lang': 'fr'}},
    {'name': 'C', 'ages': [[1, 2], [3, 4]]},
  ]
  dataset = make_test_data(items)

  not_exists_filter: UnaryFilterTuple = ('name', 'not_exists')
  result = dataset.select_rows(['info'], filters=[not_exists_filter])
  assert list(result) == [{'info': {'lang': 'fr'}}]

  not_exists_filter = ('info.lang', 'not_exists')
  result = dataset.select_rows(['name'], filters=[not_exists_filter])
  assert list(result) == [{'name': 'C'}]

  not_exists_filter = ('ages', 'not_exists')
  result = dataset.select_rows(['name'], filters=[not_exists_filter])
  assert list(result) == [{'name': 'A'}, {'name': None}]

  result = dataset.select_rows(['name'], filters=[('info', 'not_exists')])
  assert list(result) == [{'name': 'C'}]


def test_map_dtype(make_test_data: TestDataMaker) -> None:
  items = [
    {'column': {'a': 1.0, 'b': 2.0}},
    {'column': {'b': 2.5}},
    {'column': {'a': 3.0, 'c': 3.5}},
  ]
  map_dtype = MapType(key_type='string', value_field=field('float32'))
  data_schema = schema({'column': Field(dtype=map_dtype)})
  dataset = make_test_data(items, schema=data_schema)

  result = dataset.select_rows(['column'], filters=[('column.a', 'greater', 2.0)])
  assert list(result) == [
    {'column': {'key': ['a', 'c'], 'value': [3.0, 3.5]}},
  ]

  result = dataset.select_rows(['column'], filters=[('column.b', 'less_equal', 2.0)])
  assert list(result) == [{'column': {'key': ['a', 'b'], 'value': [1.0, 2.0]}}]

  result = dataset.select_rows(['column'], filters=[('column.a', 'exists')])
  assert list(result) == [
    {'column': {'key': ['a', 'b'], 'value': [1.0, 2.0]}},
    {'column': {'key': ['a', 'c'], 'value': [3.0, 3.5]}},
  ]
