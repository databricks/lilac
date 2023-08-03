"""Interface for storing vectors."""

import abc
from typing import Iterable, Optional, Type

import numpy as np

from ..schema import SpanVector, VectorKey


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
  def get(self, keys: Optional[Iterable[VectorKey]] = None) -> np.ndarray:
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
           keys: Optional[Iterable[VectorKey]] = None) -> list[tuple[VectorKey, float]]:
    """Return the top k most similar vectors.

    Args:
      query: The query vector.
      k: The number of results to return.
      keys: Optional keys to restrict the search to.

    Returns
      A list of (key, score) tuples.
    """
    raise NotImplementedError


PathKey = VectorKey


class VectorDBIndex:
  """Stores and retrives span vectors.

  This wraps a regular vector store by adding a mapping from path keys, such as (uuid1, 0),
  to span keys, such as (uuid1, 0, 0), which denotes the first span in the (uuid1, 0) text document.
  """

  def __init__(self, vector_store_cls: Type[VectorStore],
               spans: list[tuple[PathKey, list[tuple[int, int]]]], embeddings: np.ndarray) -> None:
    vector_keys = [(*path_key, i) for path_key, spans in spans for i in range(len(spans))]
    self._vector_store = vector_store_cls()
    self._vector_store.add(vector_keys, embeddings)
    # Map a path key to spans for that path.
    self._id_to_spans: dict[PathKey, list[tuple[int, int]]] = {}
    self._id_to_spans.update(spans)

  def get_vector_store(self) -> VectorStore:
    """Return the vector store."""
    return self._vector_store

  def get(self, keys: Iterable[PathKey]) -> Iterable[list[SpanVector]]:
    """Return the spans with vectors for each key in `keys`.

    Args:
      keys: The keys to return the vectors for.

    Returns
      The span vectors for the given keys.
    """
    all_spans: list[list[tuple[int, int]]] = []
    vector_keys: list[VectorKey] = []
    for path_key in keys:
      spans = self._id_to_spans[path_key]
      all_spans.append(spans)
      vector_keys.extend([(*path_key, i) for i in range(len(spans))])

    all_vectors = self._vector_store.get(vector_keys)
    offset = 0
    for spans in all_spans:
      vectors = all_vectors[offset:offset + len(spans)]
      yield [{'span': span, 'vector': vector} for span, vector in zip(spans, vectors)]
      offset += len(spans)

  def topk(self,
           query: np.ndarray,
           k: int,
           path_keys: Optional[Iterable[PathKey]] = None) -> list[tuple[PathKey, float]]:
    """Return the top k most similar vectors.

    Args:
      query: The query vector.
      k: The number of results to return.
      path_keys: Optional key prefixes to restrict the search to.

    Returns
      A list of (key, score) tuples.
    """
    vector_keys: Optional[list[VectorKey]] = None
    if path_keys is not None:
      vector_keys = [
        (*path_key, i) for path_key in path_keys for i in range(len(self._id_to_spans[path_key]))
      ]
    vector_key_scores = self._vector_store.topk(query, k, vector_keys)
    path_key_scores: dict[PathKey, float] = {}
    for (*path_key_list, _), score in vector_key_scores:
      path_key = tuple(path_key_list)
      if path_key not in path_key_scores:
        path_key_scores[path_key] = score
    return list(path_key_scores.items())
