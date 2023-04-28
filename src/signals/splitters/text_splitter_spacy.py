"""Text splitters using spaCy."""
from typing import Any, Iterable, Optional

import spacy
from spacy import Language
from typing_extensions import override

from ...schema import (
    DataType,
    EnrichmentType,
    Entity,
    EntityField,
    Field,
    ItemValue,
    RichData,
    TextSpan,
)
from ...signals.signal import Signal


class SentenceSplitterSpacy(Signal):
  """Splits documents into sentences."""
  name = 'sentences_spacy'
  enrichment_type = EnrichmentType.TEXT

  spacy_pipeline: str = 'en'

  _tokenizer: Language

  def __init__(self, spacy_pipeline: str = 'en', **kwargs: dict[Any, Any]):
    super().__init__(spacy_pipeline=spacy_pipeline, **kwargs)
    self._tokenizer = spacy.blank(spacy_pipeline)
    self._tokenizer.add_pipe('sentencizer')

  @override
  def fields(self) -> Field:
    return Field(repeated_field=EntityField(Field(dtype=DataType.STRING_SPAN)))

  @override
  def compute(self, data: Iterable[RichData]) -> Iterable[Optional[ItemValue]]:
    text_data = (row if isinstance(row, str) else '' for row in data)
    for doc in self._tokenizer.pipe(text_data):
      sentences = doc.sents
      result = [Entity(TextSpan(start=token.start_char, end=token.end_char)) for token in sentences]
      if result:
        yield result
      else:
        yield None
