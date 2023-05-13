"""Test signal base class."""
from typing import Iterable, Optional

import pytest
from typing_extensions import override

from ..schema import DataType, Field, ItemValue, RichData, SignalInputType
from .signal import Signal, clear_signal_registry, get_signal_cls, register_signal, resolve_signal


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


@pytest.fixture(scope='module', autouse=True)
def setup_teardown() -> Iterable[None]:
  # Setup.
  register_signal(TestSignal)

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
