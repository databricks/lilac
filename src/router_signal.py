"""Router for the signal registry."""

from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel
from pyparsing import Any

from .router_utils import RouteErrorHandler
from .schema import SignalInputType
from .signals.signal import SIGNAL_REGISTRY, get_signal_type

router = APIRouter(route_class=RouteErrorHandler)


class SignalInfo(BaseModel):
  """Information about a signal."""
  name: str
  input_type: SignalInputType
  # This comes from the signal types defined in signal.py. When a signal has a signal_type, they can
  # be used to filter pydantic fields that have the openapi "extra" key SIGNAL_TYPE_PYDANTIC_FIELD.
  signal_type: Optional[str]
  json_schema: dict[str, Any]


@router.get('/', response_model_exclude_none=True)
def get_signals() -> list[SignalInfo]:
  """List the datasets."""
  return [
    SignalInfo(
      name=s.name, input_type=s.input_type, signal_type=get_signal_type(s), json_schema=s.schema())
    for s in SIGNAL_REGISTRY.values()
  ]
