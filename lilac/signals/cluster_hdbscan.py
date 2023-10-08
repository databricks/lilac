"""Compute clusters for a dataset."""
from typing import ClassVar, Iterable, Optional

import numpy as np
import umap
from pydantic import Field as PyField
from sklearn.cluster import HDBSCAN
from typing_extensions import override

from lilac.embeddings.vector_store import VectorDBIndex
from lilac.utils import DebugTimer

from ..embeddings.embedding import get_embed_fn
from ..schema import Field, Item, PathKey, RichData, SignalInputType, SpanVector, field, lilac_span
from ..signal import VectorSignal

CLUSTER_ID = 'cluster_id'
MIN_CLUSTER_SIZE = 5
DBSCAN_EPS = 0.05


class ClusterHDBScan(VectorSignal):
  """Find clusters of documents in a dataset using pre-computed embeddings and DBSCAN."""
  name: ClassVar[str] = 'cluster_hdbscan'
  display_name: ClassVar[str] = 'Cluster with HDBSCAN'
  input_type: ClassVar[SignalInputType] = SignalInputType.TEXT

  min_cluster_size: int = PyField(
    title='Minimum cluster size',
    default=MIN_CLUSTER_SIZE,
    description='The minimum number of samples in a neighborhood.')

  @override
  def fields(self) -> Field:
    return field(
      fields=[field(dtype='string_span', fields={CLUSTER_ID: field('int32', categorical=True)})])

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

    all_spans: list[list[tuple[int, int]]] = []
    all_vectors: list[np.ndarray] = []
    with DebugTimer('DBSCAN: Reading from vector store'):
      for vectors in span_vectors:
        all_spans.append([vector['span'] for vector in vectors])
        for vector in vectors:
          all_vectors.append(vector['vector'])

    # Use UMAP to reduce the dimensionality before hdbscan to speed up clustering.
    # For details on hyperparameters, see:
    # https://umap-learn.readthedocs.io/en/latest/clustering.html
    reducer = umap.UMAP(n_components=10, n_neighbors=30, min_dist=0.0)
    all_vectors = reducer.fit_transform(all_vectors)

    hdbscan = HDBSCAN(min_cluster_size=self.min_cluster_size, n_jobs=-1)
    hdbscan.fit(np.array(all_vectors))

    span_index = 0
    for spans in all_spans:
      span_clusters: list[Item] = []
      for span in spans:
        cluster_id: Optional[int] = int(hdbscan.labels_[span_index])
        start, end = span
        if cluster_id == -1:
          cluster_id = None
        span_clusters.append(lilac_span(start, end, {CLUSTER_ID: cluster_id}))
        span_index += 1

      yield span_clusters
