"""HNSW vector store."""

import multiprocessing
import threading
from typing import Iterable, Optional, Set, cast

import hnswlib
import numpy as np
import pandas as pd
from typing_extensions import override

from ..schema import VectorKey
from ..utils import DebugTimer
from .vector_store import VectorStore

_HNSW_SUFFIX = '.hnswlib.bin'
_LOOKUP_SUFFIX = '.lookup.pkl'

# Parameters for HNSW index: https://github.com/nmslib/hnswlib/blob/master/ALGO_PARAMS.md
QUERY_EF = 50
CONSTRUCTION_EF = 100
M = 16
SPACE = 'ip'


class HNSWVectorStore(VectorStore):
  """HNSW-backed vector store."""

  name = 'hnsw'

  def __init__(self) -> None:
    # Maps a `VectorKey` to a row index in `_embeddings`.
    self._key_to_label: Optional[pd.Series] = None
    self._index: Optional[hnswlib.Index] = None
    self._lock = threading.Lock()

  @override
  def save(self, base_path: str) -> None:
    assert (
      self._key_to_label is not None and self._index is not None
    ), 'The vector store has no embeddings. Call load() or add() first.'
    with self._lock:
      self._index.save_index(base_path + _HNSW_SUFFIX)
      self._key_to_label.to_pickle(base_path + _LOOKUP_SUFFIX)

  @override
  def load(self, base_path: str) -> None:
    with self._lock:
      self._key_to_label = pd.read_pickle(base_path + _LOOKUP_SUFFIX)
      dim = int(self._key_to_label.name)
      index = hnswlib.Index(space=SPACE, dim=dim)
      index.set_num_threads(multiprocessing.cpu_count())
      index.load_index(base_path + _HNSW_SUFFIX)
      self._index = index
      index.set_ef(min(QUERY_EF, self.size()))

  @override
  def size(self) -> int:
    assert (
      self._index is not None
    ), 'The vector store has no embeddings. Call load() or add() first.'
    return self._index.get_current_count()

  @override
  def add(self, keys: list[VectorKey], embeddings: np.ndarray) -> None:
    with self._lock:
      dim = embeddings.shape[1]

      current_size = self.size() if self._index is not None else 0
      if self._index is None:
        with DebugTimer('hnswlib index creation'):
          index = hnswlib.Index(space=SPACE, dim=dim)
          index.set_num_threads(multiprocessing.cpu_count())
          index.init_index(max_elements=len(keys), ef_construction=CONSTRUCTION_EF, M=M)
          self._index = index
      else:
        with DebugTimer('hnswlib index resize'):
          self._index.resize_index(current_size + len(keys))

      if len(keys) != embeddings.shape[0]:
        raise ValueError(
          f'Length of keys ({len(keys)}) does not match number of embeddings {embeddings.shape[0]}.'
        )

      with DebugTimer('hnswlib add items'):
        # Cast to float32 since dot product with float32 is 40-50x faster than float16 and 2.5
        # faster than float64.
        embeddings = embeddings.astype(np.float32)
        row_indices = np.arange(current_size, current_size + len(keys), dtype=np.int32)

        new_key_to_label = pd.Series(row_indices, index=keys, dtype=np.int32)
        if self._key_to_label is not None:
          self._key_to_label = pd.concat([self._key_to_label, new_key_to_label])
        else:
          self._key_to_label = new_key_to_label

        self._key_to_label.name = str(dim)
        self._index.add_items(embeddings, row_indices)
        self._index.set_ef(min(QUERY_EF, self.size()))

  @override
  def get(self, keys: Optional[Iterable[VectorKey]] = None) -> np.ndarray:
    assert (
      self._index is not None and self._key_to_label is not None
    ), 'No embeddings exist in this store.'
    with self._lock:
      if not keys:
        return np.array(self._index.get_items(self._key_to_label.values), dtype=np.float32)
      locs = self._key_to_label.loc[cast(list[str], keys)].values
      return np.array(self._index.get_items(locs), dtype=np.float32)

  @override
  def topk(
    self, query: np.ndarray, k: int, keys: Optional[Iterable[VectorKey]] = None
  ) -> list[tuple[VectorKey, float]]:
    assert (
      self._index is not None and self._key_to_label is not None
    ), 'No embeddings exist in this store.'
    with self._lock:
      labels: Set[int] = set()
      if keys is not None:
        labels = set(self._key_to_label.loc[cast(list[str], keys)].tolist())
        k = min(k, len(labels))

      k = min(k, self.size())

      def filter_func(label: int) -> bool:
        return label in labels

      query = np.expand_dims(query.astype(np.float32), axis=0)
      try:
        locs, dists = self._index.knn_query(query, k=k, filter=filter_func if labels else None)
      except RuntimeError:
        # If K is too large compared to M and construction-time ef, HNSW will throw an error.
        # In this case we return no results, which is ok for the caller of this method
        # (VectorIndex).
        return []
      locs = locs[0]
      dists = dists[0]
      topk_keys = self._key_to_label.index.values[locs]
      return [(key, 1 - dist) for key, dist in zip(topk_keys, dists)]
