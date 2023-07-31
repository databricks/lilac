"""Test the semantic search signal."""

from typing import Iterable, Optional, cast

import numpy as np
import pytest
from pytest_mock import MockerFixture
from typing_extensions import override

from ..data.dataset_test_utils import make_vector_index
from ..data.dataset_utils import lilac_embedding, lilac_span
from ..embeddings.vector_store import VectorStore
from ..schema import Item, RichData, VectorKey
from .semantic_similarity import SemanticSimilaritySignal
from .signal import TextEmbeddingSignal, clear_signal_registry, register_signal

EMBEDDINGS: dict[VectorKey, list[list[float]]] = {
  ('1',): [[1.0, 0.0, 0.0]],
  ('2',): [[0.9, 0.1, 0.0]],
  ('3',): [[0.0, 0.0, 1.0]]
}

STR_EMBEDDINGS: dict[str, list[float]] = {
  'hello': [1.0, 0.0, 0.0],
  'hello world': [0.9, 0.1, 0.0],
  'far': [0.0, 0.0, 1.0]
}


class TestVectorStore(VectorStore):
  """A test vector store with fixed embeddings."""

  @override
  def keys(self) -> list[VectorKey]:
    return []

  @override
  def add(self, keys: list[VectorKey], embeddings: np.ndarray) -> None:
    # We fix the vectors for the test vector store.
    pass

  @override
  def get(self, keys: Optional[Iterable[VectorKey]] = None) -> np.ndarray:
    keys = keys or []
    return np.array([EMBEDDINGS[tuple(path_key)][cast(int, index)] for *path_key, index in keys])


class TestEmbedding(TextEmbeddingSignal):
  """A test embed function."""
  name = 'test_embedding'

  @override
  def compute(self, data: Iterable[RichData]) -> Iterable[Item]:
    """Embed the examples, use a hashmap to the vector for simplicity."""
    for example in data:
      yield [lilac_embedding(0, len(example), np.array(STR_EMBEDDINGS[cast(str, example)]))]


@pytest.fixture(scope='module', autouse=True)
def setup_teardown() -> Iterable[None]:
  # Setup.
  register_signal(TestEmbedding)

  # Unit test runs.
  yield

  # Teardown.
  clear_signal_registry()


def test_semantic_similarity_compute_keys(mocker: MockerFixture) -> None:
  vector_index = make_vector_index(TestVectorStore, EMBEDDINGS)

  embed_mock = mocker.spy(TestEmbedding, 'compute')

  signal = SemanticSimilaritySignal(query='hello', embedding=TestEmbedding.name)
  scores = list(signal.vector_compute([('1',), ('2',), ('3',)], vector_index))

  # Embeddings should be called only 1 time for the search.
  assert embed_mock.call_count == 1

  assert scores == [
    [lilac_span(0, 0, {'score': 1})],
    [lilac_span(0, 0, {'score': 0.9})],
    [lilac_span(0, 0, {'score': 0})],
  ]


def test_semantic_similarity_compute_data(mocker: MockerFixture) -> None:
  embed_mock = mocker.spy(TestEmbedding, 'compute')

  signal = SemanticSimilaritySignal(query='hello', embedding=TestEmbedding.name)
  # Compute over the text.
  scores = list(signal.compute(STR_EMBEDDINGS.keys()))

  # Embeddings should be called only 2 times, once for the search, once for the query itself.
  assert embed_mock.call_count == 2

  assert scores == [
    [lilac_span(0, 5, {'score': 1})],
    [lilac_span(0, 11, {'score': 0.9})],
    [lilac_span(0, 3, {'score': 0})],
  ]
