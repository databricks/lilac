"""Compute clusters for a dataset."""
from typing import ClassVar, Iterable, Optional

import numpy as np
from sklearn.cluster import DBSCAN
from typing_extensions import override

from lilac.embeddings.vector_store import VectorDBIndex
from lilac.utils import DebugTimer

from ..embeddings.embedding import get_embed_fn
from ..schema import Field, Item, PathKey, RichData, SignalInputType, SpanVector, field
from ..signal import VectorSignal

CLUSTER_IDS = 'cluster_ids'
MIN_SAMPLES = 5


class ClusteringSignal(VectorSignal):
  """Find clusters of documents in a dataset."""
  name: ClassVar[str] = 'clustering'
  display_name: ClassVar[str] = 'Clustering of documents'
  input_type: ClassVar[SignalInputType] = SignalInputType.TEXT

  @override
  def fields(self) -> Field:
    return field(fields={CLUSTER_IDS: [field('int32', categorical=True)]})

  @override
  def compute(self, data: Iterable[RichData]) -> Iterable[Optional[Item]]:
    embed_fn = get_embed_fn(self.embedding, split=True)
    span_vectors = embed_fn(data)
    return self._cluster_span_vectors(span_vectors)

  @override
  def vector_compute(self, keys: Iterable[PathKey],
                     vector_index: VectorDBIndex) -> Iterable[Optional[Item]]:
    span_vectors = vector_index.get(keys)
    return self._cluster_span_vectors(span_vectors)

  def _cluster_span_vectors(self,
                            span_vectors: Iterable[list[SpanVector]]) -> Iterable[Optional[Item]]:

    span_sizes: list[int] = []
    all_vectors: list[np.ndarray] = []
    with DebugTimer('getting vectors'):
      for vectors in span_vectors:
        span_sizes.append(len(vectors))
        for vector in vectors:
          all_vectors.append(vector['vector'])

    dbscan = DBSCAN(eps=0.05, min_samples=MIN_SAMPLES, metric='cosine', n_jobs=-1)
    dbscan.fit(all_vectors)
    span_index = 0
    for num_spans in span_sizes:
      cluster_ids: list[int] = []
      for _ in range(num_spans):
        cluster_id = int(dbscan.labels_[span_index])
        cluster_ids.append(cluster_id)
        span_index += 1
      yield {CLUSTER_IDS: cluster_ids}
