"""Embedding registry."""
from typing import Union

from pydantic import StrictStr

from ..schema import DataType, Field
from ..signals.signal import Signal

DEFAULT_BATCH_SIZE = 96


class Embedding(Signal):
  """A function that embeds text or images."""

  def fields(self) -> Field:
    """Return the fields for the embedding."""
    return Field(dtype=DataType.EMBEDDING)


EmbeddingId = Union[StrictStr, Embedding]
