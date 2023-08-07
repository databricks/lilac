"""HNSW vector store."""

import multiprocessing
from typing import Iterable, Optional, cast

import hnswlib
import numpy as np
import pandas as pd
from typing_extensions import override

from ..schema import VectorKey
from ..utils import DebugTimer
from .vector_store import VectorStore

_HNSW_SUFFIX = '.hnswlib.bin'
_LOOKUP_SUFFIX = '.lookup.pkl'


class HNSWVectorStore(VectorStore):
  """HNSW-backed vector store."""

  name = 'hnsw'

  def __init__(self) -> None:
    # Maps a `VectorKey` to a row index in `_embeddings`.
    self._lookup: Optional[pd.Series] = None
    self._index: Optional[hnswlib.Index] = None

  @override
  def save(self, base_path: str) -> None:
    assert self._lookup is not None and self._index is not None, (
      'The vector store has no embeddings. Call load() or add() first.')
    self._index.save_index(base_path + _HNSW_SUFFIX)
    self._lookup.to_pickle(base_path + _LOOKUP_SUFFIX)

  @override
  def load(self, base_path: str) -> None:
    self._lookup = pd.read_pickle(base_path + _LOOKUP_SUFFIX)
    dim = int(self._lookup.name)
    with DebugTimer('Loading hnswlib index'):
      index = hnswlib.Index(space='ip', dim=dim)
      index.set_ef(10)
      index.set_num_threads(multiprocessing.cpu_count())
      index.load_index(base_path + _HNSW_SUFFIX)
    self._index = index

  @override
  def keys(self) -> list[VectorKey]:
    assert self._lookup is not None, 'No embeddings exist in this store.'
    return self._lookup.index.tolist()

  @override
  def add(self, keys: list[VectorKey], embeddings: np.ndarray) -> None:
    assert self._index is None, (
      'Embeddings already exist in this store. Upsert is not yet supported.')

    if len(keys) != embeddings.shape[0]:
      raise ValueError(
        f'Length of keys ({len(keys)}) does not match number of embeddings {embeddings.shape[0]}.')

    dim = embeddings.shape[1]
    with DebugTimer('hnswlib index creation'):
      index = hnswlib.Index(space='ip', dim=dim)
      index.set_ef(10)
      index.set_num_threads(multiprocessing.cpu_count())
      index.init_index(max_elements=len(keys), ef_construction=50, M=16)

      # Cast to float32 since dot product with float32 is 40-50x faster than float16 and 2.5x faster
      # than float64.
      embeddings = embeddings.astype(np.float32)
      row_indices = np.arange(len(keys), dtype=np.uint32)
      self._lookup = pd.Series(row_indices, index=keys, dtype=np.uint32)
      self._lookup.name = str(dim)
      index.add_items(embeddings, row_indices)
      self._index = index

  @override
  def get(self, keys: Optional[Iterable[VectorKey]] = None) -> np.ndarray:
    assert self._index is not None and self._lookup is not None, (
      'No embeddings exist in this store.')
    if not keys:
      return self._index.get_items(self._lookup.values)
    locs = self._lookup.loc[cast(list[str], keys)].values
    return self._index.get_items(locs)

  @override
  def topk(self,
           query: np.ndarray,
           k: int,
           keys: Optional[Iterable[VectorKey]] = None) -> list[tuple[VectorKey, float]]:
    assert self._index is not None and self._lookup is not None, (
      'No embeddings exist in this store.')
    row_indices: Optional[Iterable[int]] = None
    if keys is not None:
      row_indices = self._lookup.loc[cast(list[str], keys)].values

    query = np.expand_dims(query.astype(np.float32), axis=0)
    locs, scores = self._index.knn_query(query, k=k, filter=row_indices)
    locs = locs[0]
    scores = scores[0]
    topk_keys = self._lookup.index.values[locs]
    return [(key, score) for key, score in zip(topk_keys, scores)]
