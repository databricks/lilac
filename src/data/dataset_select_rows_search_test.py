"""Tests for dataset.select_rows(searches=[...])."""

from typing import Iterable, cast

import numpy as np
import pytest
from pytest import approx
from pytest_mock import MockerFixture
from sklearn.preprocessing import normalize
from typing_extensions import override

from ..concepts.concept import ExampleIn, LogisticEmbeddingModel
from ..concepts.db_concept import ConceptUpdate, DiskConceptDB
from ..db_manager import set_default_dataset_cls
from ..schema import UUID_COLUMN, Item, RichData, SignalInputType
from ..signals.concept_scorer import ConceptScoreSignal
from ..signals.semantic_similarity import SemanticSimilaritySignal
from ..signals.signal import TextEmbeddingSignal, clear_signal_registry, register_signal
from ..signals.substring_search import SubstringSignal
from .dataset import ConceptQuery, KeywordQuery, ListOp, Search, SemanticQuery, SortOrder
from .dataset_duckdb import DatasetDuckDB
from .dataset_test_utils import TestDataMaker, enriched_embedding_span, enriched_item
from .dataset_utils import lilac_embedding, lilac_span

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

EMBEDDINGS: list[tuple[str, list[float]]] = [
  ('hello.', [1.0, 0.0, 0.0]),
  ('hello2.', [1.0, 1.0, 0.0]),
  ('hello world.', [1.0, 1.0, 1.0]),
  ('hello world2.', [2.0, 1.0, 1.0]),
  ('random negative 1', [0, 0, 0.3]),
  ('random negative 2', [0, 0, 0.4]),
  ('random negative 3', [0, 0.1, 0.5]),
  ('random negative 4', [0.1, 0, 0.4]),
]

STR_EMBEDDINGS: dict[str, list[float]] = {text: embedding for text, embedding in EMBEDDINGS}


@pytest.fixture(scope='module', autouse=True)
def setup_teardown() -> Iterable[None]:
  # Setup.
  set_default_dataset_cls(DatasetDuckDB)
  register_signal(TestEmbedding)

  # Unit test runs.
  yield

  # Teardown.
  clear_signal_registry()


def test_search_keyword(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data(TEST_DATA)

  query = 'world'
  result = dataset.select_rows(
    searches=[Search(path='text', query=KeywordQuery(type='keyword', search=query))],
    combine_columns=True)

  expected_signal_udf = SubstringSignal(query=query)
  assert list(result) == [{
    UUID_COLUMN: '1',
    'text': enriched_item('hello world', {expected_signal_udf.key(): [lilac_span(6, 11)]}),
    'text2': 'again hello world'
  }, {
    UUID_COLUMN: '2',
    'text': enriched_item('looking for world in text',
                          {expected_signal_udf.key(): [lilac_span(12, 17)]}),
    'text2': 'again looking for world in text',
  }]


def test_search_keyword_special_chars(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data([{
    UUID_COLUMN: '1',
    'text': 'This is 100%',
  }, {
    UUID_COLUMN: '2',
    'text': 'This has _underscore_',
  }])

  query = '100%'
  result = dataset.select_rows(
    searches=[Search(path='text', query=KeywordQuery(type='keyword', search=query))],
    combine_columns=True)

  expected_signal_udf = SubstringSignal(query=query)
  assert list(result) == [{
    UUID_COLUMN: '1',
    'text': enriched_item('This is 100%', {expected_signal_udf.key(): [lilac_span(8, 12)]}),
  }]

  query = '_underscore_'
  result = dataset.select_rows(
    searches=[Search(path='text', query=KeywordQuery(type='keyword', search=query))],
    combine_columns=True)

  expected_signal_udf = SubstringSignal(query=query)
  assert list(result) == [{
    UUID_COLUMN: '2',
    'text': enriched_item('This has _underscore_',
                          {expected_signal_udf.key(): [lilac_span(9, 21)]}),
  }]


def test_search_keyword_multiple(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data(TEST_DATA)

  query_world = 'world'
  query_looking_world = 'looking for world'
  expected_world_udf = SubstringSignal(query=query_world)
  expected_again_looking_udf = SubstringSignal(query=query_looking_world)

  result = dataset.select_rows(
    searches=[
      Search(path='text', query=KeywordQuery(type='keyword', search=query_world)),
      Search(path='text2', query=KeywordQuery(type='keyword', search=query_looking_world)),
    ],
    combine_columns=True)

  assert list(result) == [{
    UUID_COLUMN: '2',
    'text': enriched_item('looking for world in text', {
      expected_world_udf.key(): [lilac_span(12, 17)],
    }),
    'text2': enriched_item('again looking for world in text',
                           {expected_again_looking_udf.key(): [lilac_span(6, 23)]})
  }]


def test_search_keyword_with_filters(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data(TEST_DATA)

  query = 'world'
  result = dataset.select_rows(
    filters=[(UUID_COLUMN, ListOp.IN, ['1', '3'])],
    searches=[Search(path='text', query=KeywordQuery(type='keyword', search=query))],
    combine_columns=True)

  expected_signal_udf = SubstringSignal(query=query)
  assert list(result) == [
    {
      UUID_COLUMN: '1',
      'text': enriched_item('hello world', {expected_signal_udf.key(): [lilac_span(6, 11)]}),
      'text2': 'again hello world'
    },
    # The second row doesn't match the UUID filter.
  ]


class TestEmbedding(TextEmbeddingSignal):
  """A test embed function."""
  name = 'test_embedding'

  @override
  def compute(self, data: Iterable[RichData]) -> Iterable[Item]:
    """Call the embedding function."""
    for example in data:
      embedding = np.array(STR_EMBEDDINGS[cast(str, example)])
      embedding = normalize([embedding])[0]
      yield [lilac_embedding(0, len(example), embedding)]


def test_semantic_search(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data([{
    UUID_COLUMN: '1',
    'text': 'hello world.',
  }, {
    UUID_COLUMN: '2',
    'text': 'hello world2.',
  }])

  test_embedding = TestEmbedding()
  dataset.compute_signal(test_embedding, ('text'))

  query = 'hello2.'
  result = dataset.select_rows(
    searches=[
      Search(
        path='text', query=SemanticQuery(type='semantic', search=query, embedding='test_embedding'))
    ],
    combine_columns=True)
  expected_signal_udf = SemanticSimilaritySignal(query=query, embedding='test_embedding')
  assert list(result) == [
    # Results are sorted by score desc.
    {
      UUID_COLUMN: '2',
      'text': enriched_item(
        'hello world2.', {
          test_embedding.key():
            [enriched_embedding_span(0, 13, {expected_signal_udf.key(): approx(0.916, 1e-3)})]
        })
    },
    {
      UUID_COLUMN: '1',
      'text': enriched_item(
        'hello world.', {
          test_embedding.key():
            [enriched_embedding_span(0, 12, {expected_signal_udf.key(): approx(0.885, 1e-3)})]
        })
    },
  ]


def test_concept_search(make_test_data: TestDataMaker, mocker: MockerFixture) -> None:
  concept_model_mock = mocker.spy(LogisticEmbeddingModel, 'fit')

  dataset = make_test_data([{
    UUID_COLUMN: '1',
    'text': 'hello world.',
  }, {
    UUID_COLUMN: '2',
    'text': 'hello world2.',
  }, {
    UUID_COLUMN: '3',
    'text': 'random negative 1',
  }, {
    UUID_COLUMN: '4',
    'text': 'random negative 2',
  }, {
    UUID_COLUMN: '5',
    'text': 'random negative 3',
  }, {
    UUID_COLUMN: '6',
    'text': 'random negative 4',
  }])

  test_embedding = TestEmbedding()
  dataset.compute_signal(test_embedding, ('text'))

  concept_db = DiskConceptDB()
  concept_db.create(namespace='test_namespace', name='test_concept', type=SignalInputType.TEXT)
  concept_db.edit(
    'test_namespace', 'test_concept',
    ConceptUpdate(insert=[
      ExampleIn(label=False, text='hello world.'),
      ExampleIn(label=True, text='hello world2.')
    ]))

  result = dataset.select_rows(
    searches=[
      Search(
        path='text',
        query=ConceptQuery(
          type='concept',
          concept_namespace='test_namespace',
          concept_name='test_concept',
          embedding='test_embedding'))
    ],
    filters=[(UUID_COLUMN, ListOp.IN, ['1', '2'])],
    combine_columns=True)
  expected_signal_udf = ConceptScoreSignal(
    namespace='test_namespace', concept_name='test_concept', embedding='test_embedding')

  assert list(result) == [
    # Results are sorted by score desc.
    {
      UUID_COLUMN: '2',
      'text': enriched_item(
        'hello world2.', {
          test_embedding.key():
            [enriched_embedding_span(0, 13, {expected_signal_udf.key(): approx(0.75, abs=0.25)})],
          'test_namespace/test_concept/labels': [lilac_span(0, 13, {'label': True})]
        })
    },
    {
      UUID_COLUMN: '1',
      'text': enriched_item(
        'hello world.', {
          test_embedding.key():
            [enriched_embedding_span(0, 12, {expected_signal_udf.key(): approx(0.25, abs=0.25)})],
          'test_namespace/test_concept/labels': [lilac_span(0, 12, {'label': False})]
        })
    },
  ]

  # Make sure fit was called with negative examples.
  (_, embeddings, labels, _) = concept_model_mock.call_args_list[-1].args
  assert embeddings.shape == (8, 3)
  assert labels == [
    # Negative implicit labels.
    False,
    False,
    False,
    False,
    False,
    False,
    # Explicit labels.
    False,
    True
  ]


def test_sort_override_search(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data([{
    UUID_COLUMN: '1',
    'text': 'hello world.',
    'value': 10
  }, {
    UUID_COLUMN: '2',
    'text': 'hello world2.',
    'value': 20
  }])

  test_embedding = TestEmbedding()
  dataset.compute_signal(test_embedding, ('text'))

  query = 'hello2.'
  search = Search(
    path='text', query=SemanticQuery(type='semantic', search=query, embedding='test_embedding'))

  expected_signal_udf = SemanticSimilaritySignal(query=query, embedding='test_embedding')
  expected_item_1 = {
    UUID_COLUMN: '1',
    'text': enriched_item(
      'hello world.', {
        test_embedding.key():
          [enriched_embedding_span(0, 12, {expected_signal_udf.key(): approx(0.885, 1e-3)})]
      }),
    'value': 10
  }
  expected_item_2 = {
    UUID_COLUMN: '2',
    'text': enriched_item(
      'hello world2.', {
        test_embedding.key():
          [enriched_embedding_span(0, 13, {expected_signal_udf.key(): approx(0.916, 1e-3)})]
      }),
    'value': 20
  }

  sort_order = SortOrder.ASC
  result = dataset.select_rows(
    searches=[search], sort_by=[('value',)], sort_order=sort_order, combine_columns=True)
  assert list(result) == [
    # Results are sorted by score ascending.
    expected_item_1,
    expected_item_2
  ]

  sort_order = SortOrder.DESC
  result = dataset.select_rows(
    searches=[search], sort_by=[('text',)], sort_order=sort_order, combine_columns=True)
  assert list(result) == [
    # Results are sorted by score descending.
    expected_item_2,
    expected_item_1
  ]


def test_search_keyword_and_semantic(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data([{
    UUID_COLUMN: '1',
    'text': 'hello world.',
  }, {
    UUID_COLUMN: '2',
    'text': 'hello world2.',
  }])

  test_embedding = TestEmbedding()
  dataset.compute_signal(test_embedding, ('text'))

  query = 'hello2.'
  keyword_query = 'rld2'
  result = dataset.select_rows(
    searches=[
      Search(
        path='text', query=SemanticQuery(type='semantic', search=query,
                                         embedding='test_embedding')),
      Search(path='text', query=KeywordQuery(type='keyword', search=keyword_query))
    ],
    combine_columns=True)
  expected_semantic_signal = SemanticSimilaritySignal(query=query, embedding='test_embedding')
  expected_keyword_signal = SubstringSignal(query=keyword_query)
  assert list(result) == [
    # Results are sorted by score desc.
    {
      UUID_COLUMN: '2',
      'text': enriched_item(
        'hello world2.', {
          test_embedding.key():
            [enriched_embedding_span(0, 13, {expected_semantic_signal.key(): approx(0.916, 1e-3)})],
          expected_keyword_signal.key(): [lilac_span(8, 12)],
        })
    },
    # UUID '1' is not returned because it does not match the keyword query.
  ]
