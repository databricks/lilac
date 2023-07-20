"""Router for the signal registry."""

import math
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from .router_utils import RouteErrorHandler
from .schema import SignalInputType
from .signals.signal import SIGNAL_REGISTRY, TextEmbeddingSignal

router = APIRouter(route_class=RouteErrorHandler)

EMBEDDING_SORT_PRIORITIES = ['sbert', 'openai']


class SignalInfo(BaseModel):
  """Information about a signal."""
  name: str
  input_type: SignalInputType
  json_schema: dict[str, Any]


@router.get('/', response_model_exclude_none=True)
def get_signals() -> list[SignalInfo]:
  """List the signals."""
  return [
    SignalInfo(name=s.name, input_type=s.input_type, json_schema=s.schema())
    for s in SIGNAL_REGISTRY.values()
    if not issubclass(s, TextEmbeddingSignal)
  ]


@router.get('/embeddings', response_model_exclude_none=True)
def get_embeddings() -> list[SignalInfo]:
  """List the embeddings."""
  embedding_infos = [
    SignalInfo(name=s.name, input_type=s.input_type, json_schema=s.schema())
    for s in SIGNAL_REGISTRY.values()
    if issubclass(s, TextEmbeddingSignal)
  ]

  # Sort the embedding infos by priority.
  embedding_infos = sorted(
    embedding_infos,
    key=lambda s: EMBEDDING_SORT_PRIORITIES.index(s.name)
    if s.name in EMBEDDING_SORT_PRIORITIES else math.inf)

  return embedding_infos
