"""Router for the signal registry."""

import math
from typing import Annotated, Any, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, validator

from .auth import UserInfo, get_session_user
from .router_utils import RouteErrorHandler, server_compute_concept
from .schema import SignalInputType
from .signals.concept_scorer import ConceptScoreSignal
from .signals.signal import SIGNAL_REGISTRY, Signal, TextEmbeddingSignal, resolve_signal

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


class SignalComputeOptions(BaseModel):
  """The request for the standalone compute signal endpoint."""
  signal: Signal
  # The inputs to compute.
  inputs: list[str]

  @validator('signal', pre=True)
  def parse_signal(cls, signal: dict) -> Signal:
    """Parse a signal to its specific subclass instance."""
    return resolve_signal(signal)


class SignalComputeResponse(BaseModel):
  """The response for the standalone compute signal endpoint."""
  items: list[Optional[dict]]


@router.get('/compute', response_model_exclude_none=True)
def compute(
    options: SignalComputeOptions,
    user: Annotated[Optional[UserInfo], Depends(get_session_user)]) -> SignalComputeResponse:
  """Compute a signal over a set of inputs."""
  signal = options.signal
  if isinstance(signal, ConceptScoreSignal):
    result = server_compute_concept(signal, options.inputs, user)
  else:
    result = list(signal.compute(options.inputs))
  return SignalComputeResponse(items=result)
