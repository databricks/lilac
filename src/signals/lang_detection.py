"""Language detection of a document."""
from typing import Iterable, Optional, cast

import langdetect
from langdetect import DetectorFactory, LangDetectException
from typing_extensions import override

from ..data.dataset_utils import lilac_span
from ..schema import Field, Item, RichData, SignalInputType, field
from .signal import TextSignal

# For consistent results.
DetectorFactory.seed = 42

LANG_CODE = 'lang_code'


class LangDetectionSignal(TextSignal):
  """Detects the language code in text.

  <br>

  Supports 55 languages returning their
  [ISO 639-1 codes](https://en.wikipedia.org/wiki/List_of_ISO_639-1_codes).
  """
  name = 'lang_detection'
  display_name = 'Language detection'

  input_type = SignalInputType.TEXT
  compute_type = SignalInputType.TEXT

  @override
  def fields(self) -> Field:
    return field(fields=[field('string_span', fields={LANG_CODE: 'string'})])

  @override
  def compute(self, data: Iterable[RichData]) -> Iterable[Optional[Item]]:
    data = cast(Iterable[str], data)
    # Split on paragraphs.
    split_symbol = '\n\n'

    for text in data:
      offset = 0
      new_offset = 0
      result: list[Item] = []
      while offset < len(text):
        new_offset = text.find(split_symbol, offset)
        if new_offset == -1:
          new_offset = len(text)
        text_span = text[offset:new_offset]
        text_span = text_span.strip()
        if text_span:
          try:
            lang_code = langdetect.detect(text_span)
            result.append(lilac_span(offset, new_offset, {LANG_CODE: lang_code}))
          except LangDetectException:
            pass
        offset = new_offset + len(split_symbol)
      yield result
