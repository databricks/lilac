"""A signal to compute semantic search for a document."""
from typing import Iterable, Optional

from typing_extensions import override

from ..embeddings.embedding_index import GetEmbeddingIndexFn
from ..schema import DataType, EnrichmentType, Field, Item, RichData
from .signal import Signal

NUM_CHARS_FEATURE_NAME = 'num_characters'


class TextStatisticsSignal(Signal):
  """A signal to compute text statistics for a document."""
  name = 'text_statistics'
  enrichment_type = EnrichmentType.TEXT

  @override
  def fields(self) -> Field:
    return Field(fields={NUM_CHARS_FEATURE_NAME: Field(dtype=DataType.INT32)})

  @override
  def compute(
      self,
      data: Optional[Iterable[RichData]] = None,
      keys: Optional[Iterable[bytes]] = None,
      get_embedding_index: Optional[GetEmbeddingIndexFn] = None) -> Iterable[Optional[Item]]:
    if data is None:
      raise ValueError('"data" is required for TextStatistics.compute().')
    if keys:
      raise ValueError('"keys" is not supported for TextStatistics.compute().')

    return [{
        NUM_CHARS_FEATURE_NAME: len(text_content)
    } if isinstance(text_content, str) else None for text_content in data]
