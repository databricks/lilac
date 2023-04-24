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
    self._embeddings = embeddings
    # np.split makes a shallow copy of each of the embeddings, so the data frame can be a shallow
    # view of the numpy array. This means the dataframe cannot be used to modify the embeddings.
    self._df = pd.DataFrame(
        {NP_EMBEDDINGS_KWD: np.split(self._embeddings.flatten(), embeddings.shape[0])},
        index=self._keys)

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
      embeddings = np.stack(self._df.loc[np_keys][NP_EMBEDDINGS_KWD])
    else:
      embeddings = self._embeddings

    return embeddings
