"""A signal to search for a substring in a document."""
import re
from typing import Any, Iterable, Optional

from typing_extensions import override

from ..schema import Field, Item, RichData, SignalInputType, field, lilac_span
from ..signal import Signal


class SubstringSignal(Signal):
  """Find a substring in a document."""
  name = 'substring_search'
  display_name = 'Substring Search'
  input_type = SignalInputType.TEXT

  query: str

  _regex: re.Pattern[str]

  def __init__(self, **kwargs: Any):
    super().__init__(**kwargs)
    self._regex = re.compile(self.query, re.IGNORECASE)

  @override
  def fields(self) -> Field:
    return field(fields=['string_span'])

  @override
  def compute(self, data: Iterable[RichData]) -> Iterable[Optional[Item]]:
    for text in data:
      if not isinstance(text, str):
        yield None
        continue
      yield [lilac_span(m.start(), m.end()) for m in self._regex.finditer(text)]
