"""Router for the signal registry."""

import math
from typing import Annotated, Any, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, SerializeAsAny, field_validator

from .auth import UserInfo, get_session_user
from .embeddings.embedding import EMBEDDING_SORT_PRIORITIES
from .router_utils import RouteErrorHandler, server_compute_concept
from .schema import Field, SignalInputType
from .signal import SIGNAL_REGISTRY, Signal, TextEmbeddingSignal, resolve_signal
from .signals.concept_scorer import ConceptSignal

router = APIRouter(route_class=RouteErrorHandler)


class SignalInfo(BaseModel):
  """Information about a signal."""

  name: str
  input_type: SignalInputType
  json_schema: dict[str, Any]


@router.get('/', response_model_exclude_none=True)
def get_signals() -> list[SignalInfo]:
  """List the signals."""
  return [
    SignalInfo(name=s.name, input_type=s.input_type, json_schema=s.model_json_schema())
    for s in SIGNAL_REGISTRY.values()
    if not issubclass(s, TextEmbeddingSignal)
  ]


@router.get('/embeddings', response_model_exclude_none=True)
def get_embeddings() -> list[SignalInfo]:
  """List the embeddings."""
  embedding_infos = [
    SignalInfo(name=s.name, input_type=s.input_type, json_schema=s.model_json_schema())
    for s in SIGNAL_REGISTRY.values()
    if issubclass(s, TextEmbeddingSignal)
  ]

  # Sort the embedding infos by priority.
  embedding_infos = sorted(
    embedding_infos,
    key=lambda s: EMBEDDING_SORT_PRIORITIES.index(s.name)
    if s.name in EMBEDDING_SORT_PRIORITIES
    else math.inf,
  )

  return embedding_infos


class SignalComputeOptions(BaseModel):
  """The request for the standalone compute signal endpoint."""

  signal: SerializeAsAny[Signal]
  # The inputs to compute.
  inputs: list[str]

  @field_validator('signal', mode='before')
  @classmethod
  def parse_signal(cls, signal: dict) -> Signal:
    """Parse a signal to its specific subclass instance."""
    return resolve_signal(signal)


class SignalComputeResponse(BaseModel):
  """The response for the standalone compute signal endpoint."""

  items: list[Any]


@router.post('/compute', response_model_exclude_none=True)
def compute(
  options: SignalComputeOptions, user: Annotated[Optional[UserInfo], Depends(get_session_user)]
) -> SignalComputeResponse:
  """Compute a signal over a set of inputs."""
  signal = options.signal
  if isinstance(signal, ConceptSignal):
    result = server_compute_concept(signal, options.inputs, user)
  else:
    signal.setup()
    result = list(signal.compute(options.inputs))
  return SignalComputeResponse(items=result)


class SignalSchemaOptions(BaseModel):
  """The request for the signal schema endpoint."""

  signal: SerializeAsAny[Signal]

  @field_validator('signal', mode='before')
  @classmethod
  def parse_signal(cls, signal: dict) -> Signal:
    """Parse a signal to its specific subclass instance."""
    return resolve_signal(signal)


class SignalSchemaResponse(BaseModel):
  """The response for the signal schema endpoint."""

  fields: Field


@router.post('/schema', response_model_exclude_none=True)
def schema(options: SignalSchemaOptions) -> SignalSchemaResponse:
  """Get the schema for a signal."""
  signal = options.signal
  return SignalSchemaResponse(fields=signal.fields())
