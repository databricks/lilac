"""Text splitters using spaCy."""
from typing import Any, Iterable, Optional

import spacy
from spacy import Language
from typing_extensions import override

from ...data.dataset_utils import lilac_span
from ...schema import Item, RichData
from ...signals.signal import TextSplitterSignal


class SentenceSplitterSpacy(TextSplitterSignal):
  """Splits documents into sentences using the SpaCy sentence tokenizer."""
  name = 'sentences'
  display_name = 'Sentence Splitter'

  language: str = 'en'

  _tokenizer: Language

  def __init__(self, **kwargs: Any):
    super().__init__(**kwargs)
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
