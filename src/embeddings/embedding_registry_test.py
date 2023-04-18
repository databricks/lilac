"""Tests for the embedding function registery."""
from typing import Iterable

import numpy as np
import pytest
from typing_extensions import override

from ..schema import EnrichmentType, RichData
from .embedding_registry import (
    Embedding,
    clear_embedding_registry,
    get_embedding_cls,
    register_embedding,
    resolve_embedding,
)


class TestEmbedding(Embedding):
  """A test embed function."""
  name = 'test_embedding'
  enrichment_type = EnrichmentType.TEXT

  @override
  def __call__(self, data: Iterable[RichData]) -> np.ndarray:
    """Call the embedding function."""
    return np.array([[1.]] * len(list(data)))


@pytest.fixture(scope='module', autouse=True)
def setup_teardown() -> Iterable[None]:
  # Setup.
  register_embedding(TestEmbedding)

  # Unit test runs.
  yield

  # Teardown.
  clear_embedding_registry()


def test_get_embedding_cls() -> None:
  """Test getting a embedding."""
  assert TestEmbedding == get_embedding_cls('test_embedding')


def test_resolve_embedding() -> None:
  """Test resolving an embedding function."""
  test_embedding = TestEmbedding()

  # Embeddings pass through.
  assert resolve_embedding(test_embedding) == test_embedding

  # Dicts resolve to the base class.
  assert resolve_embedding(test_embedding.dict()) == test_embedding

  np.testing.assert_array_equal(test_embedding(['fake', 'text']), np.array([[1.], [1.]]))
