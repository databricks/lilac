"""Test signal base class."""
from typing import Iterable, Optional

import numpy as np
import pytest
from typing_extensions import override

from ..embeddings.embedding_index import GetEmbeddingIndexFn
from ..embeddings.embedding_registry import (
    clear_embedding_registry,
    register_embed_fn,
)
from ..schema import DataType, EnrichmentType, Field, ItemValue, RichData
from .signal import Signal

TEST_EMBEDDING_NAME = 'test_embedding'


def embed(examples: Iterable[RichData]) -> np.ndarray:
  """Embed the examples, use a hashmap to the vector for simplicity."""
  return np.array([1.0])


@pytest.fixture(scope='module', autouse=True)
def setup_teardown() -> Iterable[None]:

  # We register the embed function like this so we can mock it and assert how many times its called.
  register_embed_fn(TEST_EMBEDDING_NAME)(lambda examples: embed(examples))

  # Unit test runs.
  yield

  # Teardown.
  clear_embedding_registry()


class TestSignal(Signal):
  """A test signal."""

  # Pydantic fields
  name = 'test_signal'
  enrichment_type = EnrichmentType.TEXT

  query: str

  @override
  def fields(self) -> Field:
    return Field(dtype=DataType.FLOAT32)

  @override
  def compute(
      self,
      data: Optional[Iterable[RichData]] = None,
      keys: Optional[Iterable[bytes]] = None,
      get_embedding_index: Optional[GetEmbeddingIndexFn] = None) -> Iterable[Optional[ItemValue]]:
    del data
    return []


class TestEmbeddingSignal(TestSignal):
  """A test embedding signal."""
  name = 'test_embedding_signal'
  embedding_based = True


def test_embedding_signal_throws_no_embedding() -> None:
  with pytest.raises(ValueError, match='Signal attribute "embedding" must be defined'):
    TestEmbeddingSignal(query='test')


def test_embedding_signal_serialization() -> None:
  signal = TestEmbeddingSignal(query='test', embedding='test_embedding')

  # The class variables should not be included. The embedding name should be included.
  assert signal.dict(exclude_unset=True) == {
      'signal_name': 'test_embedding_signal',
      'query': 'test',
      'embedding': TEST_EMBEDDING_NAME
  }


def test_non_embedding_signal_serialization() -> None:
  signal = TestSignal(query='test')

  # The class variables should not be included.
  assert signal.dict(exclude_unset=True) == {'signal_name': 'test_signal', 'query': 'test'}
