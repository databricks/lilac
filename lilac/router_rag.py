"""Router for RAG."""


from typing import Sequence, Union

from fastapi import APIRouter
from pydantic import BaseModel

from .db_manager import get_dataset
from .rag.rag import (
  RagGenerationResult,
  RagRetrievalResultItem,
  get_rag_generation,
  get_rag_retrieval,
)
from .router_dataset import Column, Filter
from .router_utils import RouteErrorHandler
from .schema import Path

router = APIRouter(route_class=RouteErrorHandler)


class RagRetrievalOptions(BaseModel):
  """The config for the rag retrieval."""

  dataset_namespace: str
  dataset_name: str
  embedding: str

  query: str

  # The main column that will be used for the retrieval. This should have an embedding index already
  # computed.
  path: Path
  # Columns that will be used for additional metadata information.
  metadata_columns: Sequence[Union[Column, Path]] = []
  filters: Sequence[Filter] = []

  # Hyper-parameters.
  chunk_window: int = 1
  top_k: int = 10
  similarity_threshold: float = 0.0


class RagGenerationOptions(BaseModel):
  """The config for the rag generation."""

  query: str
  retrieval_results: list[RagRetrievalResultItem]
  prompt_template: str


@router.post('/retrieval')
def retrieval(options: RagRetrievalOptions) -> list[RagRetrievalResultItem]:
  """Get the retrieval results for a prompt."""
  ds = get_dataset(options.dataset_namespace, options.dataset_name)
  return get_rag_retrieval(
    path=options.path,
    dataset=ds,
    embedding=options.embedding,
    query=options.query,
    top_k=options.top_k,
    chunk_window=options.chunk_window,
  )


@router.post('/generate')
def generate(options: RagGenerationOptions) -> RagGenerationResult:
  """Get the retrieval results for a prompt."""
  return get_rag_generation(
    query=options.query,
    retrieval_results=options.retrieval_results,
    prompt_template=options.prompt_template,
  )
