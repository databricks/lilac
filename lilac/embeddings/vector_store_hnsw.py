"""HNSW vector store."""

import multiprocessing
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

  @override
  def save(self, base_path: str) -> None:
    assert self._key_to_label is not None and self._index is not None, (
      'The vector store has no embeddings. Call load() or add() first.')
    self._index.save_index(base_path + _HNSW_SUFFIX)
    self._key_to_label.to_pickle(base_path + _LOOKUP_SUFFIX)

  @override
  def load(self, base_path: str) -> None:
    self._key_to_label = pd.read_pickle(base_path + _LOOKUP_SUFFIX)
    dim = int(self._key_to_label.name)
    index = hnswlib.Index(space=SPACE, dim=dim)
    index.set_ef(QUERY_EF)
    index.set_num_threads(multiprocessing.cpu_count())
    index.load_index(base_path + _HNSW_SUFFIX)
    self._index = index

  @override
  def size(self) -> int:
    assert self._index is not None, (
      'The vector store has no embeddings. Call load() or add() first.')
    return self._index.get_current_count()

  @override
  def add(self, keys: list[VectorKey], embeddings: np.ndarray) -> None:
    assert self._index is None, (
      'Embeddings already exist in this store. Upsert is not yet supported.')

    if len(keys) != embeddings.shape[0]:
      raise ValueError(
        f'Length of keys ({len(keys)}) does not match number of embeddings {embeddings.shape[0]}.')

    dim = embeddings.shape[1]
    with DebugTimer('hnswlib index creation'):
      index = hnswlib.Index(space=SPACE, dim=dim)
      index.set_ef(QUERY_EF)
      index.set_num_threads(multiprocessing.cpu_count())
      index.init_index(max_elements=len(keys), ef_construction=CONSTRUCTION_EF, M=M)

      # Cast to float32 since dot product with float32 is 40-50x faster than float16 and 2.5x faster
      # than float64.
      embeddings = embeddings.astype(np.float32)
      row_indices = np.arange(len(keys), dtype=np.int32)
      self._key_to_label = pd.Series(row_indices, index=keys, dtype=np.int32)
      self._key_to_label.name = str(dim)
      index.add_items(embeddings, row_indices)
      self._index = index

  @override
  def get(self, keys: Optional[Iterable[VectorKey]] = None) -> np.ndarray:
    assert self._index is not None and self._key_to_label is not None, (
      'No embeddings exist in this store.')
    if not keys:
      return np.array(self._index.get_items(self._key_to_label.values), dtype=np.float32)
    locs = self._key_to_label.loc[cast(list[str], keys)].values
    return np.array(self._index.get_items(locs), dtype=np.float32)

  @override
  def topk(self,
           query: np.ndarray,
           k: int,
           keys: Optional[Iterable[VectorKey]] = None) -> list[tuple[VectorKey, float]]:
    assert self._index is not None and self._key_to_label is not None, (
      'No embeddings exist in this store.')
    labels: Set[int] = set()
    if keys is not None:
      labels = set(self._key_to_label.loc[cast(list[str], keys)].tolist())
      k = min(k, len(labels))

    def filter_func(label: int) -> bool:
      return label in labels

    query = np.expand_dims(query.astype(np.float32), axis=0)
    locs, dists = self._index.knn_query(query, k=k, filter=filter_func if labels else None)
    locs = locs[0]
    dists = dists[0]
    topk_keys = self._key_to_label.index.values[locs]
    return [(key, 1 - dist) for key, dist in zip(topk_keys, dists)]
