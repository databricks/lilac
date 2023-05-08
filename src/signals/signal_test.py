"""Test signal base class."""
from typing import Iterable, Optional

from typing_extensions import override

from ..schema import DataType, EnrichmentType, Field, ItemValue, RichData
from .signal import Signal


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
  def compute(self, data: Iterable[RichData]) -> Iterable[Optional[ItemValue]]:
    del data
    return []


def test_signal_serialization() -> None:
  signal = TestSignal(query='test')

  # The class variables should not be included.
  assert signal.dict() == {'signal_name': 'test_signal', 'query': 'test'}
