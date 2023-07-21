"""Language detection of a document."""
from typing import TYPE_CHECKING, Iterable, Optional, cast

from typing_extensions import override

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
    return field('string')

  @override
  def compute(self, data: Iterable[RichData]) -> Iterable[Optional[Item]]:
    data = cast(Iterable[str], data)
    for text in data:
      try:
        lang_code = self._model.detect(text)
        yield lang_code
      except self._model.LangDetectException:
        yield None
