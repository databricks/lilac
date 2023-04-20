"""Interface for storing vectors."""

import abc
from typing import Iterable, Optional

import numpy as np


class VectorStore(abc.ABC):
  """Interface for storing and retrieving vectors."""

  @abc.abstractmethod
  def add(self, keys: list[str], embeddings: np.ndarray) -> None:
    """Add or edit the given keyed embeddings to the store.

    If the keys already exist they will be overwritten, acting as an "upsert".

    Args:
      keys: The keys to add the embeddings for.
      embeddings: The embeddings to add. This should be a 2D matrix with the same length as keys.
    """
    pass

  @abc.abstractmethod
  def get(self, keys: Optional[Iterable[str]]) -> np.ndarray:
    """Return the embeddings for given keys.

    Args:
      keys: The keys to return the embeddings for. If None, return all embeddings.

    Returns
      The embeddings for the given keys.
    """
    pass

  def topk(self, query: np.ndarray, k: int) -> np.ndarray:
    """Return the top k most similar vectors.

    Args:
      query: The query vector.
      k: The number of results to return.

    Returns
      A list of (id, score) tuples.
    """
    raise NotImplementedError
