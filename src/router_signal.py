"""Router for the signal registry."""

from fastapi import APIRouter
from pydantic import BaseModel
from pyparsing import Any

from .router_utils import RouteErrorHandler
from .schema import EnrichmentType
from .signals.signal_registry import SIGNAL_REGISTRY

router = APIRouter(route_class=RouteErrorHandler)


class SignalInfo(BaseModel):
  """Information about a signal."""
  name: str
  enrichment_type: EnrichmentType
  embedding_based: bool
  json_schema: dict[str, Any]


@router.get('/', response_model_exclude_unset=True)
def get_signals() -> list[SignalInfo]:
  """List the datasets."""
  return [
      SignalInfo(name=s.name,
                 enrichment_type=s.enrichment_type,
                 embedding_based=s.embedding_based,
                 json_schema=s.schema()) for s in SIGNAL_REGISTRY.values()
  ]
