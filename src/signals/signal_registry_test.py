"""Tests for the signal registry."""
from typing import Iterable, Optional

import pytest
from typing_extensions import override

from ..embeddings.embedding_index import GetEmbeddingIndexFn
from ..schema import DataType, EnrichmentType, Field, ItemValue, Path, RichData
from ..signals.signal_registry import (
    clear_signal_registry,
    get_signal_cls,
    register_signal,
    resolve_signal,
)
from .signal import Signal


class TestSignal(Signal):
  """A test signal."""

  # Pydantic fields
  name = 'test_signal'
  enrichment_type = EnrichmentType.TEXT

  query: str

  @override
  def fields(self, input_column: Path) -> Field:
    return Field(dtype=DataType.FLOAT32)

  @override
  def compute(
      self,
      data: Optional[Iterable[RichData]] = None,
      keys: Optional[Iterable[bytes]] = None,
      get_embedding_index: Optional[GetEmbeddingIndexFn] = None) -> list[Optional[ItemValue]]:
    del data
    return []


@pytest.fixture(scope='module', autouse=True)
def setup_teardown() -> Iterable[None]:
  # Setup.
  register_signal(TestSignal)

  # Unit test runs.
  yield

  # Teardown.
  clear_signal_registry()


def test_get_signal_cls() -> None:
  """Test getting a signal."""
  assert TestSignal == get_signal_cls('test_signal')


def test_resolve_signal() -> None:
  """Test resolving a signal."""
  test_signal = TestSignal(query='hello')

  # Signals pass through.
  assert resolve_signal(test_signal) == test_signal

  # Dicts resolve to the base class.
  assert resolve_signal(test_signal.dict()) == test_signal
