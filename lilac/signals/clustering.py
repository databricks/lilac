"""Compute clusters for a dataset."""
from typing import Iterable, Optional

from typing_extensions import override

from lilac.embeddings.vector_store import VectorDBIndex

from ..embeddings.embedding import EmbedFn
from ..schema import Field, Item, PathKey, RichData, SignalInputType, SpanVector, field
from ..signal import VectorSignal

CLUSTER_KEY = 'cluster_id'


class Clustering(VectorSignal):
  """Find clusters of documents in a dataset."""
  name = 'clustering'
  display_name = 'Clustering of documents'
  input_type = SignalInputType.TEXT

  _embed_fn: EmbedFn

  @override
  def fields(self) -> Field:
    return field(fields={CLUSTER_KEY: field('uint32', categorical=True)})

  @override
  def compute(self, data: Iterable[RichData]) -> Iterable[Optional[Item]]:
    span_vectors = self._embed_fn(data)
    return self._score_span_vectors(span_vectors)

  @override
  def vector_compute(self, keys: Iterable[PathKey],
                     vector_index: VectorDBIndex) -> Iterable[Optional[Item]]:
    span_vectors = vector_index.get(keys)
    return self._score_span_vectors(span_vectors)

  def _score_span_vectors(self,
                          span_vectors: Iterable[Iterable[SpanVector]]) -> Iterable[Optional[Item]]:

    return flat_batched_compute(
      span_vectors, f=self._compute_span_vector_batch, batch_size=_BATCH_SIZE)
