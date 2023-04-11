"""Manage FastAPI background tasks."""

import functools
import uuid
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Awaitable, Callable, Optional, Union

from dask.distributed import Client, Variable
from pydantic import BaseModel

from .utils import log

TaskId = str
Task = Union[Callable[..., Any], Callable[..., Awaitable[Any]]]


class TaskStatus(str, Enum):
  """Enum holding a tasks status."""
  PENDING = 'pending'
  COMPLETED = 'completed'


class TaskInfo(BaseModel):
  """Metadata about a task."""
  name: str
  status: TaskStatus
  progress: Optional[float]
  description: Optional[str]
  start_timestamp: str
  end_timestamp: Optional[str]


class TaskManifest(BaseModel):
  """Information for tasks that are running or completed."""
  tasks: dict[str, TaskInfo]


class TaskManager():
  """Manage FastAPI background tasks."""
  _tasks: dict[str, TaskInfo] = {}

  def __init__(self, dask_client: Optional[Client] = None) -> None:
    """By default, use a dask multi-processing client.

    A user can pass in a dask client to use a different executor.
    """
    self._dask_client = dask_client or Client()

  def manifest(self) -> TaskManifest:
    """Get all tasks."""
    # If the task has not completed, read the progress from dask.
    for task_id, task in self._tasks.items():
      if task.status != TaskStatus.COMPLETED:
        task.progress = _progress_variable(task_id).get()

    return TaskManifest(tasks=self._tasks)

  def task_id(self, name: str, description: Optional[str] = None) -> TaskId:
    """Create a unique ID for a task."""
    task_id = uuid.uuid4().bytes.hex()
    self._tasks[task_id] = TaskInfo(name=name,
                                    status=TaskStatus.PENDING,
                                    progress=None,
                                    description=description,
                                    start_timestamp=datetime.now().isoformat())
    _progress_variable(task_id).set(0.0)
    return task_id

  def _set_task_completed(self, task_id: TaskId) -> None:
    self._tasks[task_id].status = TaskStatus.COMPLETED
    self._tasks[task_id].progress = 1.0
    end_timestamp = datetime.now().isoformat()
    self._tasks[task_id].end_timestamp = end_timestamp

    _progress_variable(task_id).delete()

    elapsed = datetime.fromisoformat(end_timestamp) - datetime.fromisoformat(
        self._tasks[task_id].start_timestamp)
    log(f'Task completed "{task_id}": "{self._tasks[task_id].name}" in '
        f'{_pretty_timedelta(elapsed)}.')

  def execute(self, task_id: str, task: Task, *args: Any) -> None:
    """Create a unique ID for a task."""
    log(f'Scheduling task "{task_id}": "{self._tasks[task_id].name}".')

    task_future = self._dask_client.submit(task, *args, key=task_id)
    task_future.add_done_callback(lambda _: self._set_task_completed(task_id))

  def stop(self) -> None:
    """Stop the task manager and close the dask client."""
    self._dask_client.close()


@functools.cache
def task_manager() -> TaskManager:
  """The global singleton for the task manager."""
  return TaskManager()


def _progress_variable(task_id: TaskId) -> Variable:
  """Return the name of the progress variable for a task."""
  return Variable(f'{task_id}_progress')


def set_worker_task_progress(task_id: TaskId, progress: float) -> None:
  """Updates a task with a progress between 0 and 1.

  This method does not exist on the TaskManager as it is meant to be a standalone method used by
  workers running tasks on separate processes so does not have access to task manager state.
  """
  _progress_variable(task_id).set(progress)


def _pretty_timedelta(delta: timedelta) -> str:
  seconds = delta.total_seconds()
  days, seconds = divmod(seconds, 86400)
  hours, seconds = divmod(seconds, 3600)
  minutes, seconds = divmod(seconds, 60)
  if days > 0:
    return '%dd%dh%dm%ds' % (days, hours, minutes, seconds)
  elif hours > 0:
    return '%dh%dm%ds' % (hours, minutes, seconds)
  elif minutes > 0:
    return '%dm%ds' % (minutes, seconds)
  else:
    return '%ds' % (seconds,)
