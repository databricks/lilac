"""Tests for dataset.select_rows(searches=[...])."""

from typing import Iterable, cast

import numpy as np
import pytest
from pytest import approx
from sklearn.preprocessing import normalize
from typing_extensions import override

from ..schema import UUID_COLUMN, Item, RichData
from ..signals.semantic_similarity import SemanticSimilaritySignal
from ..signals.signal import TextEmbeddingSignal, clear_signal_registry, register_signal
from ..signals.substring_search import SubstringSignal
from .dataset import ListOp, SearchType
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

EMBEDDINGS: list[tuple[str, list[float]]] = [('hello.', [1.0, 0.0, 0.0]),
                                             ('hello2.', [1.0, 1.0, 0.0]),
                                             ('hello world.', [1.0, 1.0, 1.0]),
                                             ('hello world2.', [2.0, 1.0, 1.0])]

STR_EMBEDDINGS: dict[str, list[float]] = {text: embedding for text, embedding in EMBEDDINGS}


@pytest.fixture(scope='module', autouse=True)
def setup_teardown() -> Iterable[None]:
  # Setup.
  register_signal(TestEmbedding)

  # Unit test runs.
  yield

  # Teardown.
  clear_signal_registry()


def test_search_like(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data(TEST_DATA)

  query = 'world'
  result = dataset.select_rows(
    searches=[('text', SearchType.CONTAINS, 'world', None)], combine_columns=True)
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


def test_search_like_multiple(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data(TEST_DATA)

  query_world = 'world'
  query_looking_world = 'looking for world'
  expected_world_udf = SubstringSignal(query=query_world)
  expected_again_looking_udf = SubstringSignal(query=query_looking_world)

  result = dataset.select_rows(
    searches=[('text', SearchType.CONTAINS, query_world, None),
              ('text2', SearchType.CONTAINS, query_looking_world, None)],
    combine_columns=True)

  assert list(result) == [{
    UUID_COLUMN: '2',
    'text': enriched_item('looking for world in text', {
      expected_world_udf.key(): [lilac_span(12, 17)],
    }),
    'text2': enriched_item('again looking for world in text',
                           {expected_again_looking_udf.key(): [lilac_span(6, 23)]})
  }]


def test_search_like_with_filters(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data(TEST_DATA)

  query = 'world'
  result = dataset.select_rows(
    filters=[(UUID_COLUMN, ListOp.IN, ['1', '3'])],
    searches=[('text', SearchType.CONTAINS, 'world', None)],
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
    searches=[('text', SearchType.SEMANTIC, query, 'test_embedding')], combine_columns=True)
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
