"""Language detection of a document."""
import re
from typing import TYPE_CHECKING, Iterable, Optional, cast

from pydantic import Field as PydanticField
from typing_extensions import override

from ..data.dataset_utils import lilac_span
from ..schema import Field, Item, RichData, SignalInputType, field
from .signal import TextSignal

LANG_CODE = 'lang_code'

if TYPE_CHECKING:
  import langdetect


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

  split_by_paragraph = PydanticField(
    False, description='Compute language scores for each paragraph.')

  _model: 'langdetect'

  @override
  def setup(self) -> None:
    try:
      import langdetect
      langdetect.DetectorFactory.seed = 42  # For consistent results.
    except ImportError:
      raise ImportError('Could not import the "langdetect" python package. '
                        'Please install it with `pip install langdetect`.')
    self._model = langdetect

  @override
  def fields(self) -> Field:
    if self.split_by_paragraph:
      return field(fields=[field('string_span', fields={LANG_CODE: 'string'})])
    return field('string')

  @override
  def compute(self, data: Iterable[RichData]) -> Iterable[Optional[Item]]:
    data = cast(Iterable[str], data)
    # Split on paragraphs.
    split_symbol = re.compile('(\r?\n){2,}')

    for text in data:
      if not self.split_by_paragraph:
        try:
          yield self._model.detect(text)
        except self._model.LangDetectException:
          yield None
        continue

      prev_end = 0
      result: list[Item] = []
      for m in split_symbol.finditer(text):
        start, end = m.span()
        text_span = text[prev_end:start]
        text_span = text_span.strip()
        if text_span:
          try:
            lang_code = self._model.detect(text_span)
            result.append(lilac_span(prev_end, start, {LANG_CODE: lang_code}))
          except self._model.LangDetectException:
            pass
        prev_end = end

      # Process the last chunk.
      text_span = text[prev_end:]
      if text_span.strip():
        try:
          lang_code = self._model.detect(text_span)
          result.append(lilac_span(prev_end, len(text), {LANG_CODE: lang_code}))
        except self._model.LangDetectException:
          pass

      yield result
