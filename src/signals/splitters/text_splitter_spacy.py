"""Text splitters using spaCy."""
from typing import Any, Iterable, Optional

import spacy
from spacy import Language
from typing_extensions import override

from ...data.dataset_utils import lilac_span, signal_item
from ...schema import ItemValue, RichData
from ...signals.signal import TextSplitterSignal


class SentenceSplitterSpacy(TextSplitterSignal):
  """Splits documents into sentences."""
  name = 'sentences_spacy'

  spacy_pipeline: str = 'en'

  _tokenizer: Language

  def __init__(self, spacy_pipeline: str = 'en', **kwargs: dict[Any, Any]):
    super().__init__(spacy_pipeline=spacy_pipeline, **kwargs)
    self._tokenizer = spacy.blank(spacy_pipeline)
    self._tokenizer.add_pipe('sentencizer')

  @override
  def compute(self, data: Iterable[RichData]) -> Iterable[Optional[ItemValue]]:
    text_data = (row if isinstance(row, str) else '' for row in data)
    for doc in self._tokenizer.pipe(text_data):
      sentences = doc.sents
      result = [signal_item(lilac_span(token.start_char, token.end_char)) for token in sentences]
      if result:
        yield result
      else:
        yield None
