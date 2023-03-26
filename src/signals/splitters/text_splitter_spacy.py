"""Text splitters using spaCy."""
from typing import Any, Callable, Iterable, Optional

from spacy import Language
from typing_extensions import override  # type: ignore

from ...embeddings.embedding_index import EmbeddingIndex
from ...embeddings.embedding_registry import EmbeddingId
from ...schema import EnrichmentType, Field, Item
from ...signals.signal import Signal
from .spacy_utils import load_spacy
from .splitter import SpanFields, SpanItem

SENTENCES_FEATURE_NAME = 'sentences'


class SentenceSplitterSpacy(Signal):
  """Splits documents into sentences."""
  name = 'sentences_spacy'
  enrichment_type = EnrichmentType.TEXT

  spacy_pipeline: str

  _tokenizer: Language

  def __init__(self, spacy_pipeline: str = 'en_core_web_sm', **kwargs: dict[Any, Any]):
    super().__init__(spacy_pipeline=spacy_pipeline, **kwargs)
    self._tokenizer = load_spacy(spacy_pipeline)

  @override
  def fields(self) -> dict[str, Field]:
    return {SENTENCES_FEATURE_NAME: Field(repeated_field=Field(fields=SpanFields({})))}

  @override
  def compute(
      self,
      data: Optional[Iterable[str]] = None,
      keys: Optional[Iterable[bytes]] = None,
      get_embedding_index: Optional[Callable[[EmbeddingId, Iterable[bytes]], EmbeddingIndex]] = None
  ) -> Iterable[Item]:
    if data is None:
      raise ValueError('Sentence splitter requires text data.')

    for text in data:
      sentences = self._tokenizer(text).sents
      yield {
          SENTENCES_FEATURE_NAME: [
              SpanItem(span=(token.start_char, token.end_char)) for token in sentences
          ]
      }
