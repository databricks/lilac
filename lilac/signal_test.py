"""Test signal base class."""
from typing import ClassVar, Iterable, Optional

import pytest
from typing_extensions import override

from .schema import Field, Item, RichData, SignalInputType, field
from .signal import (
  Signal,
  TextEmbeddingSignal,
  clear_signal_registry,
  get_signal_by_type,
  get_signal_cls,
  get_signals_by_type,
  register_signal,
  resolve_signal,
)


class TestSignal(Signal):
  """A test signal."""

  # Pydantic fields
  name: ClassVar[str] = 'test_signal'
  input_type: ClassVar[SignalInputType] = SignalInputType.TEXT

  query: str

  @override
  def fields(self) -> Field:
    return field('float32')

  @override
  def compute(self, data: Iterable[RichData]) -> Iterable[Optional[Item]]:
    del data
    return []


class TestTextEmbedding(TextEmbeddingSignal):
  """A test text embedding."""

  name: ClassVar[str] = 'test_embedding'

  @override
  def compute(self, data: Iterable[RichData]) -> Iterable[Optional[Item]]:
    del data
    return []


@pytest.fixture(scope='module', autouse=True)
def setup_teardown() -> Iterable[None]:
  # Setup.
  register_signal(TestSignal)
  register_signal(TestTextEmbedding)

  # Unit test runs.
  yield

  # Teardown.
  clear_signal_registry()


def test_signal_serialization() -> None:
  signal = TestSignal(query='test')

  # The class variables should not be included.
  assert signal.model_dump() == {'signal_name': 'test_signal', 'query': 'test'}


def test_get_signal_cls() -> None:
  """Test getting a signal."""
  assert TestSignal == get_signal_cls('test_signal')


def test_resolve_signal() -> None:
  """Test resolving a signal."""
  test_signal = TestSignal(query='hello')

  # Signals pass through.
  assert resolve_signal(test_signal) == test_signal

  # Dicts resolve to the base class.
  assert resolve_signal(test_signal.model_dump()) == test_signal


def test_get_signal_by_type() -> None:
  assert get_signal_by_type(TestTextEmbedding.name, TextEmbeddingSignal) == TestTextEmbedding


def test_get_signal_by_type_validation() -> None:
  with pytest.raises(ValueError, match='Signal "invalid_signal" not found in the registry'):
    get_signal_by_type('invalid_signal', TestTextEmbedding)

  with pytest.raises(ValueError, match=f'"{TestSignal.name}" is a `{TestSignal.__name__}`'):
    get_signal_by_type(TestSignal.name, TextEmbeddingSignal)


def test_get_signals_by_type() -> None:
  assert get_signals_by_type(TextEmbeddingSignal) == [TestTextEmbedding]


class TestSignalNoDisplayName(Signal):
  name: ClassVar[str] = 'signal_no_name'


class TestSignalDisplayName(Signal):
  name: ClassVar[str] = 'signal_display_name'
  display_name: ClassVar[str] = 'test display name'


def test_signal_title_schema() -> None:
  assert TestSignalNoDisplayName.model_json_schema()['title'] == TestSignalNoDisplayName.__name__
  assert TestSignalDisplayName.model_json_schema()['title'] == 'test display name'
