"""Utils for writing the embedding index for a column."""
import abc
from typing import Callable, Iterable, Optional

import numpy as np
from pydantic import BaseModel

from ..embeddings.embedding_registry import Embedding, EmbeddingId
from ..schema import Path, RichData
from ..tasks import TaskId


class EmbeddingIndex(BaseModel):
  """The result of an embedding index query."""

  class Config:
    arbitrary_types_allowed = True

  embeddings: np.ndarray


GetEmbeddingIndexFn = Callable[[EmbeddingId, Iterable[bytes]], EmbeddingIndex]


class EmbeddingIndexer(abc.ABC):
  """An interface for embedding indexers."""

  @abc.abstractmethod
  def get_embedding_index(self,
                          column: Path,
                          embedding: EmbeddingId,
                          keys: Optional[Iterable[bytes]] = None) -> EmbeddingIndex:
    """Get an embedding index for a column, throw if it doesn't exist.

    Args:
      column: The column to get the embedding index for.
      embedding_id: The embedding to use.
      keys: The keys to get the embedding index for. If None, get the embedding index for all
        keys.

    Returns
      The embedding index for the given column and embedding.
    """
    pass

  @abc.abstractmethod
  def compute_embedding_index(self,
                              column: Path,
                              embedding: Embedding,
                              keys: Iterable[bytes],
                              data: Iterable[RichData],
                              task_id: Optional[TaskId] = None) -> None:
    """Get an embedding index for a column, throw if it doesn't exist.

    Args:
      column: The column to get the embedding index for.
      embedding: The embedding to use.
      keys: The keys to use for the embedding index. This should align with data.
      data: The rich data to compute the embedding index for.

    Returns
      The embedding index for the given column and embedding.
    """
    pass
