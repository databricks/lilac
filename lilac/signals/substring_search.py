"""A signal to search for a substring in a document."""
from typing import ClassVar, Iterable, Optional

from typing_extensions import override

from ..schema import Field, Item, RichData, SignalInputType, field, lilac_span
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


class SubstringSignal(Signal):
  """Find a substring in a document."""

  name: ClassVar[str] = 'substring_search'
  display_name: ClassVar[str] = 'Substring Search'
  input_type: ClassVar[SignalInputType] = SignalInputType.TEXT

  query: str

  @override
  def fields(self) -> Field:
    return field(fields=['string_span'])

  @override
  def compute(self, data: Iterable[RichData]) -> Iterable[Optional[Item]]:
    for text in data:
      if not isinstance(text, str):
        yield None
        continue
      yield [lilac_span(start, end) for start, end in _find_all(text, self.query)]
