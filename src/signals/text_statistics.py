"""Compute text statistics for a document."""
from typing import Iterable, Optional

from typing_extensions import override

from ..schema import DataType, Field, Item, RichData
from .signal import TextSignal

NUM_CHARS_FEATURE_NAME = 'num_characters'


class TextStatisticsSignal(TextSignal):
  """Compute text statistics for a document."""
  name = 'text_statistics'

  @override
  def fields(self) -> Field:
    return Field(fields={NUM_CHARS_FEATURE_NAME: Field(dtype=DataType.INT32)})

  @override
  def compute(self, data: Iterable[RichData]) -> Iterable[Optional[Item]]:
    return ({
      NUM_CHARS_FEATURE_NAME: len(text_content)
    } if isinstance(text_content, str) else None for text_content in data)
