"""NumpyVectorStore class for storing vectors in numpy arrays."""

from typing import Iterable, Optional

import numpy as np
import pandas as pd
from typing_extensions import override

from .vector_store import VectorStore

NP_INDEX_KEYS_KWD = 'keys'
NP_EMBEDDINGS_KWD = 'embeddings'


class NumpyVectorStore(VectorStore):
  """Stores vectors as in-memory np arrays."""
  _embeddings: np.ndarray
  _keys: np.ndarray
  _df: pd.DataFrame

  @override
  def add(self, keys: list[str], embeddings: np.ndarray) -> None:
    if hasattr(self, '_embeddings') or hasattr(self, '_keys'):
      raise ValueError('Embeddings already exist in this store. Upsert is not yet supported.')

    if len(keys) != embeddings.shape[0]:
      raise ValueError(
          f'Length of keys ({len(keys)}) does not match number of embeddings {embeddings.shape[0]}.'
      )

    self._keys = np.array(keys)
    # Cast to float32 since dot product with float32 is 40-50x faster than float16 and 2.5x faster
    # than float64.
    self._embeddings = embeddings.astype(np.float32)
    # np.split makes a shallow copy of each of the embeddings, so the data frame can be a shallow
    # view of the numpy array. This means the dataframe cannot be used to modify the embeddings.
    self._df = pd.DataFrame(
        {NP_EMBEDDINGS_KWD: np.split(self._embeddings.flatten(), embeddings.shape[0])},
        index=self._keys)

  @override
  def get(self, keys: Iterable[str]) -> np.ndarray:
    """Return the embeddings for given keys.

    Args:
      keys: The keys to return the embeddings for.

    Returns
      The embeddings for the given keys.
    """
    if isinstance(keys, pd.Series):
      np_keys = keys.to_numpy()
    else:
      np_keys = np.array(keys)

    return np.stack(self._df.loc[np_keys][NP_EMBEDDINGS_KWD])

  @override
  def topk(self,
           query: np.ndarray,
           k: int,
           keys: Optional[Iterable[str]] = None) -> list[tuple[str, float]]:
    if keys:
      embeddings = self.get(keys)
      keys = np.array(keys)
    else:
      embeddings = self._embeddings
      keys = self._keys

    query = query.astype(embeddings.dtype)
    similarities: np.ndarray = np.dot(embeddings, query).flatten()
    k = min(k, len(similarities))

    # We do a partition + sort only top K to save time: O(n + klogk) instead of O(nlogn).
    idx = np.argpartition(similarities, -k)[-k:]
    # Indices sorted by value from largest to smallest.
    idx = idx[np.argsort(similarities[idx])][::-1]

    topk_similarities = similarities[idx]
    topk_keys = keys[idx]
    return list(zip(topk_keys, topk_similarities))
