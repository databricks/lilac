"""The configuration for the RAG."""
from typing import Sequence, Union

from pydantic import BaseModel

from ..data.dataset import Column, Filter
from ..schema import Path


class RagRetrievalConfig(BaseModel):
  """The request for the select rows endpoint."""

  column: Union[Column, Path]
  filters: Sequence[Filter] = []

  chunk_window: int = 1
  top_k: int = 10
  similarity_threshold: float = 0.0


class RagRetrievalResponse(BaseModel):
  """The response of the RAG retrieval model."""

  pass


class RagConfig(BaseModel):
  pass
