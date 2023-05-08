"""Test the semantic search signal."""

from typing import Iterable, cast

import numpy as np
from pytest_mock import MockerFixture
from typing_extensions import override

from ..embeddings.embedding import EmbeddingSignal
from ..embeddings.vector_store import VectorStore
from ..schema import EmbeddingEntity, EnrichmentType, Item, PathTuple, RichData
from .semantic_search import SemanticSearchSignal

TEST_EMBEDDING_NAME = 'test_embedding'

EMBEDDINGS: dict[PathTuple, list[float]] = {
  ('1',): [1.0, 0.0, 0.0],
  ('2',): [0.9, 0.1, 0.0],
  ('3',): [0.0, 0.0, 1.0]
}

STR_EMBEDDINGS: dict[str, list[float]] = {
  'hello': [1.0, 0.0, 0.0],
  'hello world': [0.9, 0.1, 0.0],
  'far': [0.0, 0.0, 1.0]
}


class TestVectorStore(VectorStore):
  """A test vector store with fixed embeddings."""

  @override
  def add(self, keys: list[PathTuple], embeddings: np.ndarray) -> None:
    # We fix the vectors for the test vector store.
    pass

  @override
  def get(self, keys: Iterable[PathTuple]) -> np.ndarray:
    keys = keys or []
    return np.array([EMBEDDINGS[row_id] for row_id in keys])


class TestEmbedding(EmbeddingSignal):
  """A test embed function."""
  name = TEST_EMBEDDING_NAME
  enrichment_type = EnrichmentType.TEXT

  @override
  def compute(self, data: Iterable[RichData]) -> Iterable[Item]:
    """Embed the examples, use a hashmap to the vector for simplicity."""
    embeddings = np.array([STR_EMBEDDINGS[cast(str, example)] for example in data])
    yield from (EmbeddingEntity(e) for e in embeddings)


def test_semantic_search_compute_keys(mocker: MockerFixture) -> None:
  vector_store = TestVectorStore()

  embed_mock = mocker.spy(TestEmbedding, 'compute')

  signal = SemanticSearchSignal(query='hello', embedding=TestEmbedding())
  scores = list(signal.vector_compute([('1',), ('2',), ('3',)], vector_store))

  # Embeddings should be called only 1 time for the search.
  assert embed_mock.call_count == 1

  assert scores == [1.0, 0.9, 0.0]


def test_semantic_search_compute_data(mocker: MockerFixture) -> None:
  embed_mock = mocker.spy(TestEmbedding, 'compute')

  signal = SemanticSearchSignal(query='hello', embedding=TestEmbedding())
  # Compute over the text.
  scores = list(signal.compute(STR_EMBEDDINGS.keys()))

  # Embeddings should be called only 2 times, once for the search, once for the query itself.
  assert embed_mock.call_count == 2

  assert scores == [1.0, 0.9, 0.0]
