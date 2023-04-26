"""Utils for writing the embedding index for a column."""
import abc
from typing import Callable, Iterable, Optional

import numpy as np
from pydantic import BaseModel, validator

from ..embeddings.embedding_registry import Embedding, EmbeddingId, resolve_embedding
from ..schema import Path, PathTuple, RichData
from ..tasks import TaskId


class EmbeddingIndex(BaseModel):
  """The result of an embedding index query."""

  class Config:
    arbitrary_types_allowed = True

  keys: list[str]
  embeddings: np.ndarray


class EmbeddingIndexInfo(BaseModel):
  """The information about an embedding index."""
  column: PathTuple
  embedding: Embedding

  @validator('embedding', pre=True)
  def parse_embedding(cls, embedding: dict) -> Embedding:
    """Parse an embedding to its specific subclass instance."""
    return resolve_embedding(embedding)


class EmbeddingIndexerManifest(BaseModel):
  """The manifest of an embedding indexer."""
  indexes: list[EmbeddingIndexInfo]


GetEmbeddingIndexFn = Callable[[EmbeddingId, Iterable[str]], EmbeddingIndex]


class EmbeddingIndexer(abc.ABC):
  """An interface for embedding indexers."""

  @abc.abstractmethod
  def manifest(self) -> EmbeddingIndexerManifest:
    """Get the manifest for this embedding indexer."""
    pass

  @abc.abstractmethod
  def get_embedding_index(self, column: Path, embedding: EmbeddingId) -> EmbeddingIndex:
    """Get an embedding index for a column, throw if it doesn't exist.

    Args:
      column: The column to get the embedding index for.
      embedding_id: The embedding to use.

    Returns
      The embedding index for the given column and embedding.
    """
    pass

  @abc.abstractmethod
  def compute_embedding_index(self,
                              column: Path,
                              embedding: Embedding,
                              keys: Iterable[str],
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
