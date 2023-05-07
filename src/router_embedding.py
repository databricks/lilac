"""Router for the signal registry."""

from fastapi import APIRouter
from pydantic import BaseModel
from pyparsing import Any

from .embeddings.embedding import EmbeddingSignal
from .router_utils import RouteErrorHandler
from .schema import EnrichmentType
from .signals.signal_registry import SIGNAL_REGISTRY

router = APIRouter(route_class=RouteErrorHandler)


class EmbeddingInfo(BaseModel):
  """Information about an embedding function."""
  name: str
  enrichment_type: EnrichmentType
  json_schema: dict[str, Any]


@router.get('/', response_model_exclude_none=True)
def get_embeddings() -> list[EmbeddingInfo]:
  """List the datasets."""
  return [
      EmbeddingInfo(name=s.name, enrichment_type=s.enrichment_type, json_schema=s.schema())
      for s in SIGNAL_REGISTRY.values()
      if issubclass(s, EmbeddingSignal)
  ]
