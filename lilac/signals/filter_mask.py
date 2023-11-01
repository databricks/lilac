"""Filters metadata based on an operatio. Internal use only for highlighting search results."""
from typing import Any, ClassVar, Iterable, Optional, Union

from typing_extensions import override

from ..data.dataset import FeatureListValue, FeatureValue, FilterOp
from ..schema import Field, Item, SignalInputType, field
from ..signal import Signal


class FilterMaskSignal(Signal):
  """Find a substring in a document."""

  name: ClassVar[str] = 'metadata_search'
  display_name: ClassVar[str] = 'Metadata Search'
  input_type: ClassVar[SignalInputType] = SignalInputType.ANY

  op: FilterOp
  value: Optional[Union[FeatureValue, FeatureListValue]] = None

  @override
  def fields(self) -> Field:
    return field(dtype='boolean')

  @override
  def compute(self, values: Iterable[Any]) -> Iterable[Optional[Item]]:
    for value in values:
      if self.op != 'equals':
        raise ValueError(f'Metadata search does not support "{self.op}" op yet.')
      yield True if value == self.value else None
