"""Utils for writing the embedding index for a column."""
import abc
from typing import Iterable, Optional

import numpy as np
from pydantic import BaseModel

from ..schema import Item, Path, PathTuple, RichData
from ..tasks import TaskId


class EmbeddingIndex(BaseModel):
  """The result of an embedding index query."""

  class Config:
    arbitrary_types_allowed = True

  keys: list[PathTuple]
  embeddings: np.ndarray


class EmbeddingIndexer(abc.ABC):
  """An interface for embedding indexers."""

  @abc.abstractmethod
  def get_embedding_index(self, column: Path) -> EmbeddingIndex:
    """Get an embedding index for a column, throw if it doesn't exist.

    Args:
      column: The column to get the embedding index for.

    Returns
      The embedding index for the given column and embedding.
    """
    pass

  @abc.abstractmethod
  def write_embedding_index(self,
                            column: Path,
                            items: Iterable[Item],
                            keys: Iterable[PathTuple],
                            data: Iterable[RichData],
                            task_id: Optional[TaskId] = None) -> None:
    """Write an embedding index for a column.

    Args:
      column: The column to get write the embedding index for.
      embedding: The embedding to use.
      keys: The keys to use for the embedding index. This should align with data.
      data: The rich data to compute the embedding index for.

    Returns
      The embedding index for the given column and embedding.
    """
    pass
