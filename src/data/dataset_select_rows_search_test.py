"""Tests for dataset.select_rows(searches=[...])."""

from ..schema import UUID_COLUMN, Item
from ..signals.substring_search import SubstringSignal
from .dataset import ListOp, SearchType
from .dataset_test_utils import TestDataMaker, expected_item
from .dataset_utils import itemize_primitives, lilac_span

TEST_DATA: list[Item] = [{
  UUID_COLUMN: '1',
  'text': 'hello world',
  'text2': 'again hello world',
}, {
  UUID_COLUMN: '2',
  'text': 'looking for world in text',
  'text2': 'again looking for world in text',
}, {
  UUID_COLUMN: '3',
  'text': 'unrelated text',
  'text2': 'again unrelated text'
}]


def test_search_like(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data(TEST_DATA)

  query = 'world'
  result = dataset.select_rows(
    searches=[('text', SearchType.CONTAINS, 'world')], combine_columns=True)

  expected_signal_udf = SubstringSignal(query=query)
  assert list(result) == itemize_primitives([{
    UUID_COLUMN: '1',
    'text': expected_item('hello world',
                          {expected_signal_udf.key(): [expected_item(lilac_span(6, 11))]}),
    'text2': 'again hello world'
  }, {
    UUID_COLUMN: '2',
    'text': expected_item('looking for world in text',
                          {expected_signal_udf.key(): [expected_item(lilac_span(12, 17))]}),
    'text2': 'again looking for world in text',
  }])


def test_search_like_multiple(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data(TEST_DATA)

  query_world = 'world'
  query_looking_world = 'looking for world'
  expected_world_udf = SubstringSignal(query=query_world)
  expected_again_looking_udf = SubstringSignal(query=query_looking_world)

  result = dataset.select_rows(
    searches=[('text', SearchType.CONTAINS, query_world),
              ('text2', SearchType.CONTAINS, query_looking_world)],
    combine_columns=True)

  assert list(result) == itemize_primitives([{
    UUID_COLUMN: '2',
    'text': expected_item('looking for world in text', {
      expected_world_udf.key(): [expected_item(lilac_span(12, 17))],
    }),
    'text2': expected_item('again looking for world in text',
                           {expected_again_looking_udf.key(): [expected_item(lilac_span(6, 23))]})
  }])


def test_search_like_with_filters(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data(TEST_DATA)

  query = 'world'
  result = dataset.select_rows(
    filters=[(UUID_COLUMN, ListOp.IN, ['1', '3'])],
    searches=[('text', SearchType.CONTAINS, 'world')],
    combine_columns=True)

  expected_signal_udf = SubstringSignal(query=query)
  assert list(result) == itemize_primitives([
    {
      UUID_COLUMN: '1',
      'text': expected_item('hello world',
                            {expected_signal_udf.key(): [expected_item(lilac_span(6, 11))]}),
      'text2': 'again hello world'
    },
    # The second row doesn't match the UUID filter.
  ])
