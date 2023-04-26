"""Test the semantic search signal."""

from typing import Iterable, cast

import numpy as np
import pytest
from pytest_mock import MockerFixture
from typing_extensions import override

from ..embeddings.embedding_registry import (
    Embedding,
    clear_embedding_registry,
    register_embedding,
)
from ..embeddings.vector_store import VectorStore
from ..schema import EnrichmentType, RichData
from .semantic_search import SemanticSearchSignal

TEST_EMBEDDING_NAME = 'test_embedding'

EMBEDDINGS: dict[str, list[float]] = {
    '1': [1.0, 0.0, 0.0],
    '2': [0.9, 0.1, 0.0],
    '3': [0.0, 0.0, 1.0]
}

STR_EMBEDDINGS: dict[str, list[float]] = {
    'hello': [1.0, 0.0, 0.0],
    'hello world': [0.9, 0.1, 0.0],
    'far': [0.0, 0.0, 1.0]
}


class TestVectorStore(VectorStore):
  """A test vector store with fixed embeddings."""

  @override
  def add(self, keys: list[str], embeddings: np.ndarray) -> None:
    # We fix the vectors for the test vector store.
    pass

  @override
  def get(self, keys: Iterable[str]) -> np.ndarray:
    keys = keys or []
    return np.array([EMBEDDINGS[row_id] for row_id in keys])


class TestEmbedding(Embedding):
  """A test embed function."""
  name = TEST_EMBEDDING_NAME
  enrichment_type = EnrichmentType.TEXT

  @override
  def __call__(self, data: Iterable[RichData]) -> np.ndarray:
    """Embed the examples, use a hashmap to the vector for simplicity."""
    return np.array([STR_EMBEDDINGS[cast(str, example)] for example in data])


@pytest.fixture(scope='module', autouse=True)
def setup_teardown() -> Iterable[None]:
  register_embedding(TestEmbedding)

  # Unit test runs.
  yield

  # Teardown.
  clear_embedding_registry()


def test_semantic_search_compute_keys(mocker: MockerFixture) -> None:
  vector_store = TestVectorStore()

  embed_mock = mocker.spy(TestEmbedding, '__call__')

  signal = SemanticSearchSignal(query='hello', embedding=TEST_EMBEDDING_NAME)
  scores = list(signal.vector_compute(['1', '2', '3'], vector_store))

  # Embeddings should be called only 1 time for the search.
  assert embed_mock.call_count == 1

  assert scores == [1.0, 0.9, 0.0]


def test_semantic_search_compute_data(mocker: MockerFixture) -> None:
  embed_mock = mocker.spy(TestEmbedding, '__call__')

  signal = SemanticSearchSignal(query='hello', embedding=TEST_EMBEDDING_NAME)
  # Compute over the text.
  scores = list(signal.compute(STR_EMBEDDINGS.keys()))

  # Embeddings should be called only 2 times, once for the search, once for the query itself.
  assert embed_mock.call_count == 2

  assert scores == [1.0, 0.9, 0.0]
