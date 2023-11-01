"""Utils for routers."""

import traceback
from typing import Callable, Iterable, Optional

from fastapi import HTTPException, Request, Response
from fastapi.routing import APIRoute

from .auth import UserInfo
from .concepts.db_concept import DISK_CONCEPT_DB, DISK_CONCEPT_MODEL_DB
from .schema import Item, RichData
from .signals.concept_scorer import ConceptSignal


class RouteErrorHandler(APIRoute):
  """Custom APIRoute that handles application errors and exceptions."""

  def get_route_handler(self) -> Callable:
    """Get the route handler."""
    original_route_handler = super().get_route_handler()

    async def custom_route_handler(request: Request) -> Response:
      try:
        return await original_route_handler(request)
      except Exception as ex:
        if isinstance(ex, HTTPException):
          raise ex

        print('Route error:', request.url)
        print(traceback.format_exc())

        # wrap error into pretty 500 exception
        detail = ''.join(traceback.format_exception_only(type(ex), ex))
        raise HTTPException(status_code=500, detail=detail) from ex

    return custom_route_handler


def server_compute_concept(
  signal: ConceptSignal, examples: Iterable[RichData], user: Optional[UserInfo]
) -> list[Optional[Item]]:
  """Compute a concept from the REST endpoints."""
  # TODO(nsthorat): Move this to the setup() method in the concept_scorer.
  concept = DISK_CONCEPT_DB.get(signal.namespace, signal.concept_name, user)
  if not concept:
    raise HTTPException(
      status_code=404, detail=f'Concept "{signal.namespace}/{signal.concept_name}" was not found'
    )
  DISK_CONCEPT_MODEL_DB.sync(
    signal.namespace, signal.concept_name, signal.embedding, user=user, create=True
  )
  texts = [example or '' for example in examples]
  return list(signal.compute(texts))
