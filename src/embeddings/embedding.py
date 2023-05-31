"""Embedding registry."""
from typing import Callable, Iterable, Union

import numpy as np
from pydantic import StrictStr

from ..schema import RichData
from ..signals.signal import EMBEDDING_KEY, TextEmbeddingSignal, get_signal_by_type

EmbeddingId = Union[StrictStr, TextEmbeddingSignal]

EmbedFn = Callable[[Iterable[RichData]], np.ndarray]


def get_embed_fn(embedding_name: str) -> EmbedFn:
  """Return a function that returns the embedding matrix for the given embedding signal."""
  embedding = get_signal_by_type(embedding_name, TextEmbeddingSignal)(split=False)

  def _embed_fn(data: Iterable[RichData]) -> np.ndarray:
    items = embedding.compute(data)

    embedding_vectors: list[np.ndarray] = []
    for item in items:
      if not item:
        raise ValueError('Embedding signal returned None.')
      if len(item) != 1:
        raise ValueError(
          f'Embedding signal returned {len(item)} items, but expected 1 since split was False')
      embedding_vector = item[0][EMBEDDING_KEY]
      if not isinstance(embedding_vector, np.ndarray):
        raise ValueError(
          f'Embedding signal returned {type(embedding_vector)} which is not an ndarray.')
      # We use squeeze here because embedding functions can return outer dimensions of 1.
      embedding_vector = embedding_vector.squeeze()
      if embedding_vector.ndim != 1:
        raise ValueError(f'Expected embeddings to be 1-dimensional, got {embedding_vector.ndim} '
                         f'with shape {embedding_vector.shape}.')
      embedding_vectors.append(embedding_vector)
    return np.array(embedding_vectors)

  return _embed_fn
