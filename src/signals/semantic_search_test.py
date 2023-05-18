"""Test the semantic search signal."""

from typing import Iterable, cast

import numpy as np
import pytest
from pytest_mock import MockerFixture
from typing_extensions import override

from ..embeddings.vector_store import VectorStore
from ..schema import RichData, SignalOut, VectorKey
from .semantic_search import SemanticSearchSignal
from .signal import TextEmbeddingSignal, clear_signal_registry, register_signal

EMBEDDINGS: dict[VectorKey, list[float]] = {
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
  def add(self, keys: list[VectorKey], embeddings: np.ndarray) -> None:
    # We fix the vectors for the test vector store.
    pass

  @override
  def get(self, keys: Iterable[VectorKey]) -> np.ndarray:
    keys = keys or []
    return np.array([EMBEDDINGS[row_id] for row_id in keys])


class TestEmbedding(TextEmbeddingSignal):
  """A test embed function."""
  name = 'test_embedding'

  @override
  def compute(self, data: Iterable[RichData]) -> Iterable[SignalOut]:
    """Embed the examples, use a hashmap to the vector for simplicity."""
    yield from [np.array(STR_EMBEDDINGS[cast(str, example)]) for example in data]


@pytest.fixture(scope='module', autouse=True)
def setup_teardown() -> Iterable[None]:
  # Setup.
  register_signal(TestEmbedding)

  # Unit test runs.
  yield

  # Teardown.
  clear_signal_registry()


def test_semantic_search_compute_keys(mocker: MockerFixture) -> None:
  vector_store = TestVectorStore()

  embed_mock = mocker.spy(TestEmbedding, 'compute')

  signal = SemanticSearchSignal(query='hello', embedding=TestEmbedding.name)
  scores = list(signal.vector_compute([('1',), ('2',), ('3',)], vector_store))

  # Embeddings should be called only 1 time for the search.
  assert embed_mock.call_count == 1

  assert scores == [1.0, 0.9, 0.0]


def test_semantic_search_compute_data(mocker: MockerFixture) -> None:
  embed_mock = mocker.spy(TestEmbedding, 'compute')

  signal = SemanticSearchSignal(query='hello', embedding=TestEmbedding.name)
  # Compute over the text.
  scores = list(signal.compute(STR_EMBEDDINGS.keys()))

  # Embeddings should be called only 2 times, once for the search, once for the query itself.
  assert embed_mock.call_count == 2

  assert scores == [1.0, 0.9, 0.0]
