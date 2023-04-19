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

  @override
  def add(self, keys: list[str], embeddings: np.ndarray) -> None:
    if self._embeddings is not None:
      raise ValueError('Cannot add to a vector store that already has data.')
    if len(keys) != embeddings.shape[0]:
      raise ValueError(
          f'Length of keys ({len(keys)}) does not match number of embeddings {embeddings.shape[0]}.'
      )

    self._keys = np.array(keys)
    self._embeddings = embeddings

  @override
  def get(self, keys: Optional[Iterable[str]]) -> np.ndarray:
    """Return the embeddings for given keys.

    Args:
      keys: The keys to return the embeddings for. If None, return all embeddings.

    Returns
      The embeddings for the given keys.
    """
    np_keys: Optional[np.ndarray] = None
    if keys is not None:
      if isinstance(keys, pd.Series):
        np_keys = keys.to_numpy()
      else:
        np_keys = np.array(keys)

    if np_keys is not None:
      # NOTE: Calling tolist() here is necessary because we can't put the entire matrix into the
      # dataframe. This will store each embedding a list. This could be sped up if we write our
      # own implementation, or use something faster.
      # NOTE: We should potentially cache the dataframe instead of caching the two arrays.
      df = pd.DataFrame({NP_EMBEDDINGS_KWD: self._embeddings.tolist()}, index=self._keys)
      embeddings = np.stack(df.loc[np_keys][NP_EMBEDDINGS_KWD])
    else:
      embeddings = self._embeddings

    return embeddings
