"""Interface for storing vectors."""

import abc
from typing import Iterable, Optional

import numpy as np

from ..schema import VectorKey


class VectorStore(abc.ABC):
  """Interface for storing and retrieving vectors."""

  @abc.abstractmethod
  def keys(self) -> list[VectorKey]:
    """Return the keys in the store."""
    pass

  @abc.abstractmethod
  def add(self, keys: list[VectorKey], embeddings: np.ndarray) -> None:
    """Add or edit the given keyed embeddings to the store.

    If the keys already exist they will be overwritten, acting as an "upsert".

    Args:
      keys: The keys to add the embeddings for.
      embeddings: The embeddings to add. This should be a 2D matrix with the same length as keys.
    """
    pass

  @abc.abstractmethod
  def get(self, keys: Iterable[VectorKey]) -> np.ndarray:
    """Return the embeddings for given keys.

    Args:
      keys: The keys to return the embeddings for. If None, return all embeddings.

    Returns
      The embeddings for the given keys.
    """
    pass

  def topk(self,
           query: np.ndarray,
           k: int,
           key_prefixes: Optional[Iterable[VectorKey]] = None) -> list[tuple[VectorKey, float]]:
    """Return the top k most similar vectors.

    Args:
      query: The query vector.
      k: The number of results to return.
      key_prefixes: Optional key prefixes to restrict the search to.

    Returns
      A list of (key, score) tuples.
    """
    raise NotImplementedError
