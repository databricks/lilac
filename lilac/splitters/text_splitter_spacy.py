"""Text splitters using spaCy."""
from typing import TYPE_CHECKING, Any, Iterable, Optional

from typing_extensions import override

from ..schema import Item, RichData, lilac_span
from ..signal import TextSplitterSignal

if TYPE_CHECKING:
  from spacy.language import Language


class SentenceSplitterSpacy(TextSplitterSignal):
  """Splits documents into sentences using the SpaCy sentence tokenizer."""
  name = 'sentences'
  display_name = 'Sentence Splitter'

  language: str = 'en'

  _tokenizer: 'Language'

  def __init__(self, **kwargs: Any):
    super().__init__(**kwargs)

  @override
  def setup(self) -> None:
    try:
      import spacy
    except ImportError:
      raise ImportError('Could not import the "spacy" python package. '
                        'Please install it with `pip install spacy`.')
    self._tokenizer = spacy.blank(self.language)
    self._tokenizer.add_pipe('sentencizer')
    # Increase the number of characters of the tokenizer as we're not using a parser or NER.
    self._tokenizer.max_length = 10_000_000

  @override
  def compute(self, data: Iterable[RichData]) -> Iterable[Optional[Item]]:
    text_data = (row if isinstance(row, str) else '' for row in data)

    for doc in self._tokenizer.pipe(text_data):
      sentences = doc.sents
      result = [lilac_span(token.start_char, token.end_char) for token in sentences]
      if result:
        yield result
      else:
        yield None

  class Config:
    # Language is required even though it has a default value.
    schema_extra = {'required': ['language']}
