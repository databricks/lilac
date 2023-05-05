"""Embedding registry."""
from typing import Callable, Iterable, Union, cast

import numpy as np
from pydantic import StrictStr

from ..schema import ENTITY_FEATURE_KEY, EmbeddingEntityField, Field, RichData
from ..signals.signal import Signal

DEFAULT_BATCH_SIZE = 96


class Embedding(Signal):
  """A function that embeds text or images."""

  def fields(self) -> Field:
    """Return the fields for the embedding."""
    return EmbeddingEntityField()


EmbeddingId = Union[StrictStr, Embedding]


def get_embed_fn(embedding: Embedding) -> Callable[[Iterable[RichData]], np.ndarray]:
  """Return the embedding matrix for the given embedding signal."""

  def _embed_fn(data: Iterable[RichData]) -> np.ndarray:
    items = embedding.compute(data)

    # We use stack here since it works with both matrices and vectors.
    embeddings = [cast(np.ndarray, cast(dict, item)[ENTITY_FEATURE_KEY]) for item in items]
    return np.array(embeddings)

  return _embed_fn
