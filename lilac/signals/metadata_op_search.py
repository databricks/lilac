"""A signal to filter metadata based on an operation."""
from typing import Any, ClassVar, Iterable, Optional, Union

from typing_extensions import override

from ..data.dataset import FeatureListValue, FeatureValue, FilterOp
from ..schema import Field, Item, SignalInputType, field
from ..signal import Signal


def _find_all(text: str, subtext: str) -> Iterable[tuple[int, int]]:
  # Ignore casing.
  text = text.lower()
  subtext = subtext.lower()
  subtext_len = len(subtext)
  start = 0
  while True:
    start = text.find(subtext, start)
    if start == -1:
      return
    yield start, start + subtext_len
    start += subtext_len


class MetadataOpSignal(Signal):
  """Find a substring in a document."""
  name: ClassVar[str] = 'metadata_search'
  display_name: ClassVar[str] = 'Metadata Search'
  input_type: ClassVar[SignalInputType] = SignalInputType.ANY

  op: FilterOp
  value: Optional[Union[FeatureValue, FeatureListValue]] = None

  @override
  def fields(self) -> Field:
    return field(fields=['string_span'])

  @override
  def compute(self, values: Iterable[Any]) -> Iterable[Optional[Item]]:
    for value in values:
      yield value == self.value
