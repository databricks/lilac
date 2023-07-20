"""Language detection of a document."""
from typing import TYPE_CHECKING, Iterable, Optional, cast

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
            lang_code = self._model.detect(text_span)
            result.append(lilac_span(offset, new_offset, {LANG_CODE: lang_code}))
          except self._model.LangDetectException:
            pass
        offset = new_offset + len(split_symbol)
      yield result
