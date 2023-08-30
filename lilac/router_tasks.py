"""Router for tasks."""

from fastapi import APIRouter

from .router_utils import RouteErrorHandler
from .tasks import TaskManifest, get_task_manager

router = APIRouter(route_class=RouteErrorHandler)


@router.get('/')
async def get_task_manifest() -> TaskManifest:
  """Get the tasks, both completed and pending."""
  return await get_task_manager().manifest()
