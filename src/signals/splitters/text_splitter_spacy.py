"""Text splitters using spaCy."""
from typing import Any, Iterable, Optional

import spacy
from spacy import Language
from typing_extensions import override

from ...embeddings.embedding_index import GetEmbeddingIndexFn
from ...schema import DataType, EnrichmentType, Field, ItemValue, Path, RichData, TextSpan
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
  def fields(self, input_column: Path) -> Field:
    return Field(repeated_field=Field(dtype=DataType.STRING_SPAN, refers_to=input_column))

  @override
  def compute(self,
              data: Optional[Iterable[RichData]] = None,
              keys: Optional[Iterable[bytes]] = None,
              get_embedding_index: Optional[GetEmbeddingIndexFn] = None) -> Iterable[ItemValue]:
    if data is None:
      raise ValueError('Sentence splitter requires text data.')

    for doc in self._tokenizer.pipe(data):  # type: ignore
      sentences = doc.sents
      yield [TextSpan(start=token.start_char, end=token.end_char) for token in sentences]
