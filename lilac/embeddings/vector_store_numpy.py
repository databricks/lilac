"""NumpyVectorStore class for storing vectors in numpy arrays."""

from typing import Iterable, Optional, cast

import numpy as np
import pandas as pd
from typing_extensions import override

from ..schema import VectorKey
from .vector_store import VectorStore


class NumpyVectorStore(VectorStore):
  """Stores vectors as in-memory np arrays."""
  _embeddings: np.ndarray
  _keys: list[VectorKey]
  # Maps a `VectorKey` to a row index in `_embeddings`.
  _lookup: pd.Series

  @override
  def keys(self) -> list[VectorKey]:
    return self._keys

  @override
  def add(self, keys: list[VectorKey], embeddings: np.ndarray) -> None:
    if hasattr(self, '_embeddings') or hasattr(self, '_keys'):
      raise ValueError('Embeddings already exist in this store. Upsert is not yet supported.')

    if len(keys) != embeddings.shape[0]:
      raise ValueError(
        f'Length of keys ({len(keys)}) does not match number of embeddings {embeddings.shape[0]}.')

    self._keys = keys
    # Cast to float32 since dot product with float32 is 40-50x faster than float16 and 2.5x faster
    # than float64.
    self._embeddings = embeddings.astype(np.float32)
    row_indices = np.arange(len(self._embeddings), dtype=np.uint32)
    self._lookup = pd.Series(row_indices, index=keys)

  @override
  def get(self, keys: Optional[Iterable[VectorKey]] = None) -> np.ndarray:
    """Return the embeddings for given keys.

    Args:
      keys: The keys to return the embeddings for.

    Returns
      The embeddings for the given keys.
    """
    if not keys:
      return self._embeddings
    locs = self._lookup.loc[cast(list[str], keys)]
    return self._embeddings.take(locs, axis=0)

  @override
  def topk(self,
           query: np.ndarray,
           k: int,
           keys: Optional[Iterable[VectorKey]] = None) -> list[tuple[VectorKey, float]]:
    if keys is not None:
      # This uses the hierarchical index (MutliIndex) to do a prefix lookup.
      row_indices = self._lookup.loc[cast(list[str], keys)]
      keys, embeddings = list(row_indices.index), self._embeddings.take(row_indices, axis=0)
    else:
      keys, embeddings = self._keys, self._embeddings

    query = query.astype(embeddings.dtype)
    similarities: np.ndarray = np.dot(embeddings, query).reshape(-1)
    k = min(k, len(similarities))

    # We do a partition + sort only top K to save time: O(n + klogk) instead of O(nlogn).
    indices = np.argpartition(similarities, -k)[-k:]
    # Indices sorted by value from largest to smallest.
    indices = indices[np.argsort(similarities[indices])][::-1]

    topk_similarities = similarities[indices]
    topk_keys = [keys[idx] for idx in indices]
    return list(zip(topk_keys, topk_similarities))
