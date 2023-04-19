"""Compute text statistics for a document."""
from typing import Iterable, Optional

from typing_extensions import override

from ..embeddings.vector_store import VectorStore
from ..schema import DataType, EnrichmentType, Field, Item, Path, RichData
from .signal import Signal

NUM_CHARS_FEATURE_NAME = 'num_characters'


class TextStatisticsSignal(Signal):
  """Compute text statistics for a document."""
  name = 'text_statistics'
  enrichment_type = EnrichmentType.TEXT

  @override
  def fields(self, input_column: Path) -> Field:
    return Field(fields={NUM_CHARS_FEATURE_NAME: Field(dtype=DataType.INT32)})

  @override
  def compute(self,
              data: Optional[Iterable[RichData]] = None,
              keys: Optional[Iterable[str]] = None,
              vector_store: Optional[VectorStore] = None) -> Iterable[Optional[Item]]:
    if data is None:
      raise ValueError('"data" is required for TextStatistics.compute().')
    if keys:
      raise ValueError('"keys" is not supported for TextStatistics.compute().')

    return [{
        NUM_CHARS_FEATURE_NAME: len(text_content)
    } if isinstance(text_content, str) else None for text_content in data]
