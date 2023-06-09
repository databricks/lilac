"""NumpyVectorStore class for storing vectors in numpy arrays."""

from typing import Iterable, Optional

import numpy as np
import pandas as pd
from typing_extensions import override

from ..schema import VectorKey
from .vector_store import VectorStore

NP_INDEX_KEYS_KWD = 'keys'
NP_EMBEDDINGS_KWD = 'embeddings'


class NumpyVectorStore(VectorStore):
  """Stores vectors as in-memory np arrays."""
  _embeddings: np.ndarray
  _keys: list[VectorKey]
  _df: pd.DataFrame

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

    index = pd.MultiIndex.from_tuples(keys)
    # np.split makes a shallow copy of each of the embeddings, so the data frame can be a shallow
    # view of the numpy array. This means the dataframe cannot be used to modify the embeddings.
    chunks = np.vsplit(self._embeddings, self._embeddings.shape[0])
    self._df = pd.DataFrame({NP_EMBEDDINGS_KWD: chunks}, index=index)

  @override
  def get(self, keys: Iterable[VectorKey]) -> np.ndarray:
    """Return the embeddings for given keys.

    Args:
      keys: The keys to return the embeddings for.

    Returns
      The embeddings for the given keys.
    """
    return np.concatenate(self._df.loc[keys][NP_EMBEDDINGS_KWD], axis=0)

  @override
  def topk(self,
           query: np.ndarray,
           k: int,
           key_prefixes: Optional[Iterable[VectorKey]] = None) -> list[tuple[VectorKey, float]]:
    if key_prefixes is not None:
      df = self._df.loc[key_prefixes]
      keys, embeddings = list(df.index), np.concatenate(df[NP_EMBEDDINGS_KWD], axis=0)
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
