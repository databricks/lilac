"""A signal to compute semantic search for a document."""
from typing import Any, Iterable, Optional, Union

import numpy as np
from scipy.interpolate import interp1d
from typing_extensions import override

from ..batch_utils import flat_batched_compute
from ..embeddings.embedding import EmbedFn, get_embed_fn
from ..embeddings.vector_store import VectorDBIndex
from ..schema import Field, Item, PathKey, RichData, SignalInputType, SpanVector, field, lilac_span
from ..signal import VectorSignal

_BATCH_SIZE = 4096


class SemanticSimilaritySignal(VectorSignal):
  """Compute semantic similarity for a query and a document.

  \
  This is done by embedding the query with the same embedding as the document and computing a
  a similarity score between them.
  """
  name = 'semantic_similarity'
  display_name = 'Semantic Similarity'
  input_type = SignalInputType.TEXT

  query: str

  _embed_fn: EmbedFn
  # Dot products are in the range [-1, 1]. We want to map this to [0, 1] for the similarity score
  # with a slight bias towards 1 since dot product of <0.2 is not really relevant.
  _interpolate_fn = interp1d([-1, 0.2, 1], [0, 0.5, 1])
  _search_text_embedding: Optional[np.ndarray] = None

  def __init__(self, query: Union[str, bytes], embedding: str, **kwargs: Any):
    if isinstance(query, bytes):
      raise ValueError('Image queries are not yet supported for SemanticSimilarity.')
    super().__init__(query=query, embedding=embedding, **kwargs)  # type: ignore
    self._embed_fn = get_embed_fn(embedding, split=False)

  @override
  def fields(self) -> Field:
    return field(fields=[field(dtype='string_span', fields={'score': 'float32'})])

  def _get_search_embedding(self) -> np.ndarray:
    """Return the embedding for the search text."""
    if self._search_text_embedding is None:
      span_vector = list(self._embed_fn([self.query]))[0][0]
      self._search_text_embedding = span_vector['vector'].reshape(-1)

    return self._search_text_embedding

  def _score_span_vectors(self,
                          span_vectors: Iterable[Iterable[SpanVector]]) -> Iterable[Optional[Item]]:

    return flat_batched_compute(
      span_vectors, f=self._compute_span_vector_batch, batch_size=_BATCH_SIZE)

  def _compute_span_vector_batch(self, span_vectors: Iterable[SpanVector]) -> list[Item]:
    batch_matrix = np.array([sv['vector'] for sv in span_vectors])
    spans = [sv['span'] for sv in span_vectors]
    scores = batch_matrix.dot(self._get_search_embedding()).reshape(-1).tolist()
    return [lilac_span(start, end, {'score': score}) for score, (start, end) in zip(scores, spans)]

  @override
  def compute(self, data: Iterable[RichData]) -> Iterable[Optional[Item]]:
    span_vectors = self._embed_fn(data)
    return self._score_span_vectors(span_vectors)

  @override
  def vector_compute(self, keys: Iterable[PathKey],
                     vector_index: VectorDBIndex) -> Iterable[Optional[Item]]:
    span_vectors = vector_index.get(keys)
    return self._score_span_vectors(span_vectors)

  @override
  def vector_compute_topk(
      self,
      topk: int,
      vector_index: VectorDBIndex,
      keys: Optional[Iterable[PathKey]] = None) -> list[tuple[PathKey, Optional[Item]]]:
    query = self._get_search_embedding()
    topk_keys = [key for key, _ in vector_index.topk(query, topk, keys)]
    return list(zip(topk_keys, self.vector_compute(topk_keys, vector_index)))
