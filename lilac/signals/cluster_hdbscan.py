"""Compute clusters for a dataset."""
from typing import ClassVar, Iterable, Iterator, Optional

import numpy as np
from pydantic import Field as PyField
from typing_extensions import override

from ..embeddings.embedding import get_embed_fn
from ..embeddings.vector_store import VectorDBIndex
from ..schema import Field, Item, PathKey, RichData, SignalInputType, SpanVector, field, span
from ..signal import OutputType, VectorSignal
from ..utils import DebugTimer

CLUSTER_ID = 'cluster_id'
MEMBERSHIP_PROB = 'membership_prob'
MIN_CLUSTER_SIZE = 5
UMAP_N_COMPONENTS = 10


class ClusterHDBScan(VectorSignal):
  """Find clusters of documents in a dataset using pre-computed embeddings and HDBSCAN.

  This signal requires a pre-computed embedding. It uses UMAP to reduce the dimensionality
  of the embedding before clustering with HDBSCAN.
  """

  name: ClassVar[str] = 'cluster_hdbscan'
  display_name: ClassVar[str] = 'Cluster with HDBSCAN'
  input_type: ClassVar[SignalInputType] = SignalInputType.TEXT
  output_type: OutputType = 'cluster'

  min_cluster_size: int = PyField(
    title='Minimum cluster size',
    default=MIN_CLUSTER_SIZE,
    description='The minimum number of samples in a neighborhood.',
  )

  umap_n_components: int = PyField(
    title='Dimensionality of reduced embedding by UMAP',
    default=UMAP_N_COMPONENTS,
    description='The n_components argument for UMAP. This refers to the dimensionality of the '
    'reduced embedding by UMAP before it is passed to HDBScan.',
  )

  umap_random_state: Optional[int] = PyField(description='Random seed for UMAP.', default=None)

  @override
  def fields(self) -> Field:
    return field(
      fields=[
        field(
          dtype='string_span',
          fields={CLUSTER_ID: field('int32', categorical=True), MEMBERSHIP_PROB: field('float32')},
        )
      ]
    )

  @override
  def compute(self, data: Iterable[RichData]) -> Iterator[Optional[Item]]:
    embed_fn = get_embed_fn(self.embedding, split=True)
    span_vectors = embed_fn(data)
    return self._cluster_span_vectors(span_vectors)

  @override
  def vector_compute(
    self, keys: Iterable[PathKey], vector_index: VectorDBIndex
  ) -> Iterator[Optional[Item]]:
    span_vectors = vector_index.get(keys)
    return self._cluster_span_vectors(span_vectors)

  def _cluster_span_vectors(
    self, span_vectors: Iterable[list[SpanVector]]
  ) -> Iterator[Optional[Item]]:
    # umap is expensive to import due to numba compilation; lazy import when needed.
    import umap

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
    dim = all_vectors[0].size
    with DebugTimer(
      f'UMAP: Reducing dim from {dim} to {self.umap_n_components} of {len(all_vectors)} vectors'
    ):
      n_neighbors = min(30, len(all_vectors) - 1)
      if self.umap_n_components < dim and self.umap_n_components < len(all_vectors):
        reducer = umap.UMAP(
          n_components=self.umap_n_components,
          n_neighbors=n_neighbors,
          min_dist=0.0,
          random_state=self.umap_random_state,
          n_jobs=-1,
        )
        all_vectors = reducer.fit_transform(all_vectors)

    from sklearn.cluster import HDBSCAN

    with DebugTimer('HDBSCAN: Clustering'):
      min_cluster_size = min(self.min_cluster_size, len(all_vectors))
      hdbscan = HDBSCAN(min_cluster_size=min_cluster_size, n_jobs=-1)
      hdbscan.fit(all_vectors)

    span_index = 0
    for spans in all_spans:
      span_clusters: list[Item] = []
      for text_span in spans:
        cluster_id = int(hdbscan.labels_[span_index])
        membership_prob = float(hdbscan.probabilities_[span_index])
        start, end = text_span
        metadata = {CLUSTER_ID: cluster_id, MEMBERSHIP_PROB: membership_prob}
        if cluster_id < 0:
          metadata = {CLUSTER_ID: -1}
        span_clusters.append(span(start, end, metadata))
        span_index += 1

      yield span_clusters
