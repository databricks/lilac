"""Router for the signal registry."""

from fastapi import APIRouter
from pydantic import BaseModel
from pyparsing import Any

from .router_utils import RouteErrorHandler
from .schema import SignalInputType
from .signals.signal import SIGNAL_REGISTRY, TextEmbeddingSignal

router = APIRouter(route_class=RouteErrorHandler)


class EmbeddingInfo(BaseModel):
  """Information about an embedding function."""
  name: str
  input_type: SignalInputType
  json_schema: dict[str, Any]


@router.get('/', response_model_exclude_none=True)
def get_embeddings() -> list[EmbeddingInfo]:
  """List the datasets."""
  return [
    EmbeddingInfo(name=s.name, input_type=s.input_type, json_schema=s.schema())
    for s in SIGNAL_REGISTRY.values()
    if issubclass(s, TextEmbeddingSignal)
  ]
