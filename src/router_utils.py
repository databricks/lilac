"""Utils for routers."""

import traceback
from typing import Callable

from fastapi import HTTPException, Request, Response
from fastapi.routing import APIRoute


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
        print(ex)
        print(traceback.format_exc())

        # wrap error into pretty 500 exception
        raise HTTPException(status_code=500, detail=traceback.format_exc())

    return custom_route_handler
