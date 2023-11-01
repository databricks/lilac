"""NumpyVectorStore class for storing vectors in numpy arrays."""

from typing import Iterable, Optional, cast

import numpy as np
import pandas as pd
from typing_extensions import override

from ..schema import VectorKey
from .vector_store import VectorStore

_EMBEDDINGS_SUFFIX = '.matrix.npy'
_LOOKUP_SUFFIX = '.lookup.pkl'


class NumpyVectorStore(VectorStore):
  """Stores vectors as in-memory np arrays."""

  name = 'numpy'

  def __init__(self) -> None:
    self._embeddings: Optional[np.ndarray] = None
    # Maps a `VectorKey` to a row index in `_embeddings`.
    self._key_to_index: Optional[pd.Series] = None

  @override
  def size(self) -> int:
    assert (
      self._embeddings is not None
    ), 'The vector store has no embeddings. Call load() or add() first.'
    return len(self._embeddings)

  @override
  def save(self, base_path: str) -> None:
    assert (
      self._embeddings is not None and self._key_to_index is not None
    ), 'The vector store has no embeddings. Call load() or add() first.'
    np.save(base_path + _EMBEDDINGS_SUFFIX, self._embeddings, allow_pickle=False)
    self._key_to_index.to_pickle(base_path + _LOOKUP_SUFFIX)

  @override
  def load(self, base_path: str) -> None:
    self._embeddings = np.load(base_path + _EMBEDDINGS_SUFFIX, allow_pickle=False)
    self._key_to_index = pd.read_pickle(base_path + _LOOKUP_SUFFIX)

  @override
  def add(self, keys: list[VectorKey], embeddings: np.ndarray) -> None:
    if len(keys) != embeddings.shape[0]:
      raise ValueError(
        f'Length of keys ({len(keys)}) does not match number of embeddings {embeddings.shape[0]}.'
      )

    current_size = self.size() if self._embeddings is not None else 0

    # Cast to float32 since dot product with float32 is 40-50x faster than float16 and 2.5x faster
    # than float64.
    if self._embeddings is None:
      self._embeddings = embeddings.astype(np.float32)
    else:
      self._embeddings = np.concatenate([self._embeddings, embeddings.astype(np.float32)], axis=0)

    row_indices = np.arange(current_size, current_size + len(keys), dtype=np.int32)
    new_key_to_label = pd.Series(row_indices, index=keys, dtype=np.int32)
    if self._key_to_index is not None:
      self._key_to_index = pd.concat([self._key_to_index, new_key_to_label])
    else:
      self._key_to_index = new_key_to_label

  @override
  def get(self, keys: Optional[Iterable[VectorKey]] = None) -> np.ndarray:
    assert (
      self._embeddings is not None and self._key_to_index is not None
    ), 'The vector store has no embeddings. Call load() or add() first.'
    if not keys:
      return self._embeddings
    locs = self._key_to_index.loc[cast(list[str], keys)]
    return self._embeddings.take(locs, axis=0)

  @override
  def topk(
    self, query: np.ndarray, k: int, keys: Optional[Iterable[VectorKey]] = None
  ) -> list[tuple[VectorKey, float]]:
    assert (
      self._embeddings is not None and self._key_to_index is not None
    ), 'The vector store has no embeddings. Call load() or add() first.'
    if keys is not None:
      row_indices = self._key_to_index.loc[cast(list[str], keys)]
      embeddings = self._embeddings.take(row_indices, axis=0)
      keys = list(keys)
    else:
      keys, embeddings = (
        cast(list[VectorKey], self._key_to_index.index.tolist()),
        self._embeddings,
      )

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
