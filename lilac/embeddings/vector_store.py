"""Interface for storing vectors."""

import abc
import os
import pickle
from typing import Iterable, Optional, Sequence, Type, cast

import numpy as np

from ..schema import SpanVector, VectorKey
from ..utils import open_file


class VectorStore(abc.ABC):
  """Interface for storing and retrieving vectors."""

  # The global name of the vector store.
  name: str

  @abc.abstractmethod
  def save(self, base_path: str) -> None:
    """Save the store to disk."""
    pass

  @abc.abstractmethod
  def load(self, base_path: str) -> None:
    """Load the store from disk."""
    pass

  @abc.abstractmethod
  def size(self) -> int:
    """Return the number of vectors in the store."""
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

    Returns:
      The embeddings for the given keys.
    """
    pass

  def topk(
    self, query: np.ndarray, k: int, keys: Optional[Iterable[VectorKey]] = None
  ) -> list[tuple[VectorKey, float]]:
    """Return the top k most similar vectors.

    Args:
      query: The query vector.
      k: The number of results to return.
      keys: Optional keys to restrict the search to.

    Returns:
      A list of (key, score) tuples.
    """
    raise NotImplementedError


PathKey = VectorKey

_SPANS_PICKLE_NAME = 'spans.pkl'


class VectorDBIndex:
  """Stores and retrives span vectors.

  This wraps a regular vector store by adding a mapping from path keys, such as (rowid1, 0),
  to span keys, such as (rowid1, 0, 0), which denotes the first span in the (rowid1, 0) document.
  """

  def __init__(self, vector_store: str) -> None:
    self._vector_store: VectorStore = get_vector_store_cls(vector_store)()
    # Map a path key to spans for that path.
    self._id_to_spans: dict[PathKey, list[tuple[int, int]]] = {}
    self._rowid_to_path_keys: dict[str, list[PathKey]] = {}

  def load(self, base_path: str) -> None:
    """Load the vector index from disk."""
    assert not self._id_to_spans, 'Cannot load into a non-empty index.'
    with open_file(os.path.join(base_path, _SPANS_PICKLE_NAME), 'rb') as f:
      all_spans: list[tuple[PathKey, list[tuple[int, int]]]] = pickle.load(f)
      self._id_to_spans.update(all_spans)
      for path_key, _ in all_spans:
        rowid = cast(str, path_key[0])
        self._rowid_to_path_keys.setdefault(rowid, []).append(path_key)
    self._vector_store.load(os.path.join(base_path, self._vector_store.name))

  def save(self, base_path: str) -> None:
    """Save the vector index to disk."""
    assert self._id_to_spans, 'Cannot save an empty index.'
    with open_file(os.path.join(base_path, _SPANS_PICKLE_NAME), 'wb') as f:
      pickle.dump(list(self._id_to_spans.items()), f)
    self._vector_store.save(os.path.join(base_path, self._vector_store.name))

  def add(
    self, all_spans: Sequence[tuple[PathKey, list[tuple[int, int]]]], embeddings: np.ndarray
  ) -> None:
    """Add the given spans and embeddings.

    Args:
      all_spans: The spans to initialize the index with.
      embeddings: The embeddings to initialize the index with.
    """
    vector_keys = [(*path_key, i) for path_key, spans in all_spans for i in range(len(spans))]
    assert len(vector_keys) == len(
      embeddings
    ), f'Number of spans ({len(vector_keys)}) and embeddings ({len(embeddings)}) must match.'

    self._id_to_spans.update(all_spans)
    for path_key, _ in all_spans:
      rowid = cast(str, path_key[0])
      self._rowid_to_path_keys.setdefault(rowid, []).append(path_key)

    self._vector_store.add(vector_keys, embeddings)

  def get_vector_store(self) -> VectorStore:
    """Return the underlying vector store."""
    return self._vector_store

  def get(self, keys: Iterable[PathKey]) -> Iterable[list[SpanVector]]:
    """Return the spans with vectors for each key in `keys`.

    Args:
      keys: The keys to return the vectors for.

    Returns:
      The span vectors for the given keys.
    """
    all_spans: list[list[tuple[int, int]]] = []
    all_vector_keys: list[list[VectorKey]] = []
    for path_key in keys:
      spans = self._id_to_spans.get(path_key, [])
      all_spans.append(spans)
      all_vector_keys.append([(*path_key, i) for i in range(len(spans))])

    offset = 0
    flat_vector_keys = [key for vector_keys in all_vector_keys for key in (vector_keys or [])]
    all_vectors = self._vector_store.get(flat_vector_keys)
    for spans in all_spans:
      vectors = all_vectors[offset : offset + len(spans)]
      yield [{'span': span, 'vector': vector} for span, vector in zip(spans, vectors)]
      offset += len(spans)

  def topk(
    self, query: np.ndarray, k: int, rowids: Optional[Iterable[str]] = None
  ) -> list[tuple[PathKey, float]]:
    """Return the top k most similar vectors.

    Args:
      query: The query vector.
      k: The number of results to return.
      rowids: Optional row ids to restrict the search to.

    Returns:
      A list of (rowid, score) tuples.
    """
    total_num_span_keys = self._vector_store.size()
    k = min(k, total_num_span_keys)
    span_keys: Optional[list[VectorKey]] = None
    if rowids is not None:
      span_keys = []
      for rowid in rowids:
        path_keys = self._rowid_to_path_keys.get(rowid)
        if path_keys is None:
          continue

        span_keys.extend(
          [
            (*path_key, i)
            for path_key in path_keys
            for i in range(len(self._id_to_spans[path_key]))
          ]
        )
      k = min(k, len(span_keys))
    span_k = k
    path_key_scores: dict[PathKey, float] = {}
    seen_rowids: dict[str, bool] = {}
    while (
      len(seen_rowids) < k
      and span_k <= total_num_span_keys
      and (not span_keys or span_k <= len(span_keys))
    ):
      span_k += k
      vector_key_scores = self._vector_store.topk(query, span_k, span_keys)
      for (*path_key_list, _), score in vector_key_scores:
        path_key = tuple(path_key_list)
        if path_key not in path_key_scores:
          path_key_scores[path_key] = score
        rowid = cast(str, path_key[0])
        if rowid not in seen_rowids:
          seen_rowids[rowid] = True

    top_rowids = set(list(seen_rowids.keys())[:k])
    top_path_keys = [(key, s) for (key, s) in path_key_scores.items() if key[0] in top_rowids]
    return list(top_path_keys)


VECTOR_STORE_REGISTRY: dict[str, Type[VectorStore]] = {}


def register_vector_store(vector_store_cls: Type[VectorStore]) -> None:
  """Register a vector store in the global registry."""
  if vector_store_cls.name in VECTOR_STORE_REGISTRY:
    raise ValueError(f'Vector store "{vector_store_cls.name}" has already been registered!')

  VECTOR_STORE_REGISTRY[vector_store_cls.name] = vector_store_cls


def get_vector_store_cls(vector_store_name: str) -> Type[VectorStore]:
  """Return a registered vector store given the name in the registry."""
  return VECTOR_STORE_REGISTRY[vector_store_name]


def clear_vector_store_registry() -> None:
  """Clear the vector store registry."""
  VECTOR_STORE_REGISTRY.clear()
