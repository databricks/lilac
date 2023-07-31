"""A signal to compute semantic search for a document."""
from typing import Any, Iterable, Optional, Union

import numpy as np
from scipy.interpolate import interp1d
from typing_extensions import override

from ..data.dataset_utils import lilac_span
from ..embeddings.embedding import EmbedFn, get_embed_fn
from ..embeddings.vector_store import VectorDBIndex
from ..schema import Field, Item, PathKey, RichData, SignalInputType, field
from .signal import VectorSignal


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
    # TODO(nsthorat): The embedding cls might have arguments. This needs to be resolved.
    self._embed_fn = get_embed_fn(embedding)

  @override
  def fields(self) -> Field:
    return field(fields=[field(dtype='string_span', fields={'score': 'float32'})])

  def _get_search_embedding(self) -> np.ndarray:
    """Return the embedding for the search text."""
    if self._search_text_embedding is None:
      self._search_text_embedding = self._embed_fn([self.query])[0].reshape(-1)

    return self._search_text_embedding

  @override
  def compute(self, data: Iterable[RichData]) -> Iterable[Optional[Item]]:
    embeddings = self._embed_fn(data)
    scores = embeddings.dot(self._get_search_embedding()).reshape(-1)
    for text, score in zip(data, scores):
      yield [lilac_span(0, len(text), {'score': score})]

  @override
  def vector_compute(self, keys: Iterable[PathKey],
                     vector_index: VectorDBIndex) -> Iterable[Optional[Item]]:
    all_vector_spans = vector_index.get(keys)
    query = self._get_search_embedding()
    # TODO(smilkov): Do this with batched computation.
    for vector_spans in all_vector_spans:
      embeddings = np.array([vector_span['vector'] for vector_span in vector_spans])
      scores = embeddings.dot(query).reshape(-1)
      res: Item = []
      for vector_span, score in zip(vector_spans, scores):
        start, end = vector_span['span']
        res.append(lilac_span(start, end, {'score': score}))
      yield res

  @override
  def vector_compute_topk(
      self,
      topk: int,
      vector_index: VectorDBIndex,
      keys: Optional[Iterable[PathKey]] = None) -> list[tuple[PathKey, Optional[Item]]]:
    query = self._get_search_embedding()
    topk_keys = [key for key, _ in vector_index.topk(query, topk, keys)]
    return list(zip(topk_keys, self.vector_compute(topk_keys, vector_index)))
