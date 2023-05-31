"""Compute text statistics for a document."""
from typing import Iterable, Optional

from typing_extensions import override

from ..schema import Field, Item, RichData, field
from .signal import TextSignal

NUM_CHARS_FEATURE_NAME = 'num_characters'


class TextStatisticsSignal(TextSignal):
  """Compute text statistics for a document."""
  name = 'text_statistics'
  display_name = 'Text Statistics'

  @override
  def fields(self) -> Field:
    return field(fields={NUM_CHARS_FEATURE_NAME: 'int32'})

  @override
  def compute(self, data: Iterable[RichData]) -> Iterable[Optional[Item]]:
    return ({
      NUM_CHARS_FEATURE_NAME: len(text_content)
    } if isinstance(text_content, str) else None for text_content in data)
