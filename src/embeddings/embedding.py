"""Embedding registry."""
from typing import Callable, Iterable, Union, cast

import numpy as np
from pydantic import StrictStr

from ..schema import VALUE_KEY, RichData
from ..signals.signal import TextEmbeddingSignal

EmbeddingId = Union[StrictStr, TextEmbeddingSignal]


def get_embed_fn(embedding: TextEmbeddingSignal) -> Callable[[Iterable[RichData]], np.ndarray]:
  """Return a function that returns the embedding matrix for the given embedding signal."""

  def _embed_fn(data: Iterable[RichData]) -> np.ndarray:
    items = embedding.compute(data)

    embedding_vectors: list[np.ndarray] = []
    for item in items:
      # We use squeeze here because embedding functions can return outer dimensions of 1.
      embedding_vector = cast(np.ndarray, cast(dict, item)[VALUE_KEY]).squeeze()
      if embedding_vector.ndim != 1:
        raise ValueError(f'Expected embeddings to be 1-dimensional, got {embedding_vector.ndim} '
                         f'with shape {embedding_vector.shape}.')
      embedding_vectors.append(embedding_vector)
    return np.array(embedding_vectors)

  return _embed_fn
