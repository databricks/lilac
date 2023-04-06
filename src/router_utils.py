"""Utils for routers."""

from typing import Callable

from fastapi import HTTPException, Request, Response
from fastapi.routing import APIRoute

from .utils import log


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

        log('Route error:', request.url)
        log(ex)
        # wrap error into pretty 500 exception
        raise HTTPException(status_code=500, detail=str(ex))

    return custom_route_handler
