"""A signal to compute semantic search for a document."""
from typing import Any, Iterable, Optional, Union

import numpy as np
from typing_extensions import override

from ..embeddings.embedding_registry import EmbeddingComputer, EmbeddingId
from ..embeddings.vector_store import VectorStore
from ..schema import DataType, EnrichmentType, Field, ItemValue, Path, RichData
from .signal import Signal


class SemanticSearchSignal(Signal):
  """Compute semantic search for a document."""

  name = 'semantic_search'
  enrichment_type = EnrichmentType.TEXT
  embedding_based = True

  query: Union[str, bytes]
  embedding: EmbeddingId

  _embed_fn: EmbeddingComputer
  _search_text_embedding: Optional[np.ndarray] = None

  def __init__(self, query: Union[str, bytes], embedding: EmbeddingId, **kwargs: dict[Any, Any]):
    if isinstance(query, bytes):
      raise ValueError('Image queries are not yet supported for SemanticSearch.')

    super().__init__(query=query, embedding=embedding, **kwargs)

  @override
  def fields(self, input_column: Path) -> Field:
    return Field(dtype=DataType.FLOAT32)

  def _get_search_embedding(self) -> np.ndarray:
    """Return the embedding for the search text."""
    if self._search_text_embedding is None:
      self._search_text_embedding = self._embed_fn([self.query]).flatten()
    return self._search_text_embedding

  @override
  def compute(self,
              data: Optional[Iterable[RichData]] = None,
              keys: Optional[Iterable[str]] = None,
              vector_store: Optional[VectorStore] = None) -> Iterable[Optional[ItemValue]]:
    if data and keys:
      raise ValueError('"data" and "keys" cannot both be provided for SemanticSearch.compute().')

    if data:
      text_embeddings = self._embed_fn(data)
    elif keys:
      if not vector_store:
        raise ValueError(
            '"vector_store" is required for SemanticSearch.compute() when passing "keys".')
      text_embeddings = vector_store.get(keys)

    similarities = text_embeddings.dot(self._get_search_embedding()).flatten()
    return similarities.tolist()
