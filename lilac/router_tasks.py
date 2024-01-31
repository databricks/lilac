"""Router for tasks."""

from fastapi import APIRouter

from .router_utils import RouteErrorHandler
from .tasks import TaskManifest, get_task_manager

router = APIRouter(route_class=RouteErrorHandler)


@router.get('/')
def get_task_manifest() -> TaskManifest:
  """Get the tasks, both completed and pending."""
  return get_task_manager().manifest()


@router.post('/{task_id}/cancel')
def cancel_task(task_id: str) -> None:
  """Cancel a task."""
  get_task_manager().cancel_task(task_id)
