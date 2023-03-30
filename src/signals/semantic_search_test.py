"""Test the semantic search signal."""

import sys
from typing import Iterable, Optional, cast

import numpy as np
import pytest
from pytest_mock import MockerFixture
from typing_extensions import override

from ..embeddings.embedding_index import EmbeddingIndex, EmbeddingIndexer
from ..embeddings.embedding_registry import EmbeddingId, clear_embedding_registry, register_embed_fn
from ..schema import Path, RichData
from .semantic_search import SemanticSearchSignal

TEST_EMBEDDING_NAME = 'test_embedding'

EMBEDDINGS: dict[bytes, list[float]] = {
    b'1': [1.0, 0.0, 0.0],
    b'2': [0.9, 0.1, 0.0],
    b'3': [0.0, 0.0, 1.0]
}

STR_EMBEDDINGS: dict[str, list[float]] = {
    'hello': [1.0, 0.0, 0.0],
    'hello world': [0.9, 0.1, 0.0],
    'far': [0.0, 0.0, 1.0]
}


class TestEmbeddingIndexer(EmbeddingIndexer):
  """A test embedding indexer with fixed embeddings."""

  @override
  def get_embedding_index(self,
                          column: Path,
                          embedding: EmbeddingId,
                          row_ids: Optional[Iterable[bytes]] = None) -> EmbeddingIndex:
    row_ids = row_ids or []
    return EmbeddingIndex(embeddings=np.array([EMBEDDINGS[row_id] for row_id in row_ids]))

  @override
  def compute_embedding_index(self, column: Path, embedding: EmbeddingId, keys: Iterable[bytes],
                              data: Iterable[RichData]) -> None:
    pass


def embed(examples: Iterable[RichData]) -> np.ndarray:
  """Embed the examples, use a hashmap to the vector for simplicity."""
  return np.array([STR_EMBEDDINGS[cast(str, example)] for example in examples])


@pytest.fixture(scope='module', autouse=True)
def setup_teardown() -> Iterable[None]:

  # We register the embed function like this so we can mock it and assert how many times its called.
  register_embed_fn(TEST_EMBEDDING_NAME)(lambda examples: embed(examples))

  # Unit test runs.
  yield

  # Teardown.
  clear_embedding_registry()


def test_semantic_search_compute_keys(mocker: MockerFixture) -> None:
  embedding_indexer = TestEmbeddingIndexer()

  embed_mock = mocker.spy(sys.modules[__name__], embed.__name__)

  signal = SemanticSearchSignal(query='hello', embedding=TEST_EMBEDDING_NAME)
  scores = list(
      signal.compute(keys=[b'1', b'2', b'3'],
                     get_embedding_index=lambda embedding, row_ids: embedding_indexer.
                     get_embedding_index(column='test_col', embedding=embedding, row_ids=row_ids)))

  # Embeddings should be called only 1 time for the search.
  assert embed_mock.call_count == 1

  assert scores == [1.0, 0.9, 0.0]


def test_semantic_search_compute_data(mocker: MockerFixture) -> None:
  embed_mock = mocker.spy(sys.modules[__name__], embed.__name__)

  signal = SemanticSearchSignal(query='hello', embedding=TEST_EMBEDDING_NAME)
  # Compute over the text.
  scores = list(signal.compute(data=STR_EMBEDDINGS.keys()))

  # Embeddings should be called only 2 times, once for the search, once for the query itself.
  assert embed_mock.call_count == 2

  assert scores == [1.0, 0.9, 0.0]
