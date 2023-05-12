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

    # We use stack here since it works with both matrices and vectors.
    embeddings = [cast(np.ndarray, cast(dict, item)[VALUE_KEY]) for item in items]
    return np.array(embeddings)

  return _embed_fn
