"""Test signal base class."""
from typing import Iterable, Optional

import pytest
from typing_extensions import override

from ..schema import DataType, Field, ItemValue, RichData, SignalInputType
from .signal import (
  SIGNAL_TYPE_TEXT_EMBEDDING,
  SIGNAL_TYPE_TEXT_SPLITTER,
  Signal,
  TextEmbeddingSignal,
  TextSplitterSignal,
  clear_signal_registry,
  get_signal_by_type,
  get_signal_cls,
  register_signal,
  resolve_signal,
)


class TestSignal(Signal):
  """A test signal."""

  # Pydantic fields
  name = 'test_signal'
  input_type = SignalInputType.TEXT

  query: str

  @override
  def fields(self) -> Field:
    return Field(dtype=DataType.FLOAT32)

  @override
  def compute(self, data: Iterable[RichData]) -> Iterable[Optional[ItemValue]]:
    del data
    return []


class TestTextSplitter(TextSplitterSignal):
  """A test text splitter."""
  name = 'test_text_splitter'

  @override
  def compute(self, data: Iterable[RichData]) -> Iterable[Optional[ItemValue]]:
    del data
    return []


class TestTextEmbedding(TextEmbeddingSignal):
  """A test text embedding."""
  name = 'test_text_embedding'

  @override
  def compute(self, data: Iterable[RichData]) -> Iterable[Optional[ItemValue]]:
    del data
    return []


@pytest.fixture(scope='module', autouse=True)
def setup_teardown() -> Iterable[None]:
  # Setup.
  register_signal(TestSignal)
  register_signal(TestTextSplitter)
  register_signal(TestTextEmbedding)

  # Unit test runs.
  yield

  # Teardown.
  clear_signal_registry()


def test_signal_serialization() -> None:
  signal = TestSignal(query='test')

  # The class variables should not be included.
  assert signal.dict() == {'signal_name': 'test_signal', 'query': 'test'}


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


def test_get_signal_by_type() -> None:
  assert get_signal_by_type(TestTextSplitter.name, SIGNAL_TYPE_TEXT_SPLITTER) == TestTextSplitter
  assert get_signal_by_type(TestTextEmbedding.name,
                            SIGNAL_TYPE_TEXT_EMBEDDING) == TestTextEmbedding


def test_get_signal_by_type_validation() -> None:
  with pytest.raises(ValueError, match='Signal "invalid_signal" not found in the registry'):
    get_signal_by_type('invalid_signal', SIGNAL_TYPE_TEXT_SPLITTER)

  with pytest.raises(ValueError, match='Invalid `signal_type` "invalid_type"'):
    get_signal_by_type(TestTextSplitter.name, 'invalid_type')

  with pytest.raises(
      ValueError, match=f'"{TestTextSplitter.name}" is a `{TestTextSplitter.__name__}`'):
    get_signal_by_type(TestTextSplitter.name, SIGNAL_TYPE_TEXT_EMBEDDING)
