"""A signal to compute semantic search for a document."""
from typing import Any, Callable, Iterable, Optional, Union, cast

import numpy as np
from typing_extensions import override

from ..embeddings.embedding import get_embed_fn
from ..embeddings.vector_store import VectorStore
from ..schema import DataType, Field, ItemValue, RichData, VectorKey
from .signal import TextEmbeddingModelSignal, TextEmbeddingSignal, get_signal_cls


class SemanticSearchSignal(TextEmbeddingModelSignal):
  """Compute semantic similarity for between a document.

  <br>This is done by embedding the query with the same embedding as the document and computing a
  a similarity score between them.
  """
  name = 'semantic_search'
  display_name = 'Semantic Search'

  query: str

  _embed_fn: Callable[[Iterable[RichData]], np.ndarray]
  _search_text_embedding: Optional[np.ndarray] = None

  def __init__(self, query: Union[str, bytes], embedding: str, **kwargs: dict[Any, Any]):
    if isinstance(query, bytes):
      raise ValueError('Image queries are not yet supported for SemanticSearch.')

    super().__init__(query=query, embedding=embedding, **kwargs)

    # TODO(nsthorat): The embedding cls might have arguments. This needs to be resolved.
    self._embed_fn = get_embed_fn(cast(TextEmbeddingSignal, get_signal_cls(embedding)()))

  @override
  def fields(self) -> Field:
    return Field(dtype=DataType.FLOAT32)

  def _get_search_embedding(self) -> np.ndarray:
    """Return the embedding for the search text."""
    if self._search_text_embedding is None:

      self._search_text_embedding = list(self._embed_fn([self.query]))[0].flatten()
    return self._search_text_embedding

  @override
  def compute(self, data: Iterable[RichData]) -> Iterable[Optional[ItemValue]]:
    text_embeddings = self._embed_fn(data)
    similarities = text_embeddings.dot(self._get_search_embedding()).flatten()
    return similarities.tolist()

  @override
  def vector_compute(self, keys: Iterable[VectorKey],
                     vector_store: VectorStore) -> Iterable[Optional[ItemValue]]:
    text_embeddings = vector_store.get(keys)
    similarities = text_embeddings.dot(self._get_search_embedding()).flatten()
    return similarities.tolist()
