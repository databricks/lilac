"""A signal to compute semantic search for a document."""
from typing import Any, Iterable, Optional, Union

import numpy as np
from typing_extensions import override

from ..embeddings.embedding import EmbedFn, get_embed_fn
from ..embeddings.vector_store import VectorStore
from ..schema import Field, Item, RichData, VectorKey, field
from .signal import TextEmbeddingModelSignal


class SemanticSimilaritySignal(TextEmbeddingModelSignal):
  """Compute semantic similarity for a query and a document.

  <br>This is done by embedding the query with the same embedding as the document and computing a
  a similarity score between them.
  """
  name = 'semantic_similarity'
  display_name = 'Semantic Similarity'

  query: str

  _embed_fn: EmbedFn
  _search_text_embedding: Optional[np.ndarray] = None

  def __init__(self, query: Union[str, bytes], embedding: str, **kwargs: Any):
    if isinstance(query, bytes):
      raise ValueError('Image queries are not yet supported for SemanticSimilarity.')

    super().__init__(query=query, embedding=embedding, **kwargs)

    # TODO(nsthorat): The embedding cls might have arguments. This needs to be resolved.
    self._embed_fn = get_embed_fn(embedding)

  @override
  def fields(self) -> Field:
    return field('float32')

  def _get_search_embedding(self) -> np.ndarray:
    """Return the embedding for the search text."""
    if self._search_text_embedding is None:

      self._search_text_embedding = list(self._embed_fn([self.query]))[0].flatten()
    return self._search_text_embedding

  @override
  def compute(self, data: Iterable[RichData]) -> Iterable[Optional[Item]]:
    text_embeddings = self._embed_fn(data)
    similarities = text_embeddings.dot(self._get_search_embedding()).flatten()
    return similarities.tolist()

  @override
  def vector_compute(self, keys: Iterable[VectorKey],
                     vector_store: VectorStore) -> Iterable[Optional[Item]]:
    text_embeddings = vector_store.get(keys)
    similarities = text_embeddings.dot(self._get_search_embedding()).flatten()
    return similarities.tolist()
