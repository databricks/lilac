"""Manage FastAPI background tasks."""

import functools
import traceback
import uuid
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Awaitable, Callable, Iterable, Optional, TypeVar, Union

import dask
from dask.distributed import Client, Variable
from distributed import Future, get_worker
from pydantic import BaseModel

from .utils import log

TaskId = str
Task = Union[Callable[..., Any], Callable[..., Awaitable[Any]]]


class TaskStatus(str, Enum):
  """Enum holding a tasks status."""
  PENDING = 'pending'
  COMPLETED = 'completed'
  ERROR = 'error'


class TaskInfo(BaseModel):
  """Metadata about a task."""
  name: str
  status: TaskStatus
  progress: Optional[float]
  description: Optional[str]
  start_timestamp: str
  end_timestamp: Optional[str]
  error: Optional[str]


class TaskManifest(BaseModel):
  """Information for tasks that are running or completed."""
  tasks: dict[str, TaskInfo]


PROGRESS_LOG_KEY = 'progress'


class TaskManager():
  """Manage FastAPI background tasks."""
  _tasks: dict[str, TaskInfo] = {}

  def __init__(self, dask_client: Optional[Client] = None) -> None:
    """By default, use a dask multi-processing client.

    A user can pass in a dask client to use a different executor.
    """
    # Set dasks workers to be non-daemonic so they can spawn child processes if they need to. This
    # is particularly useful for signals that use libraries with multiprocessing support.
    dask.config.set({'distributed.worker.daemon': False})

    self._dask_client = dask_client or Client(asynchronous=True)

  async def manifest(self) -> TaskManifest:
    """Get all tasks."""
    # If the task has not completed, read the progress from dask.
    for task_id, task in self._tasks.items():
      if task.status != TaskStatus.COMPLETED:
        progress_events = self._dask_client.get_events(_progress_event_topic(task_id))
        # This allows us to work with both sync and async clients.
        if not isinstance(progress_events, tuple):
          progress_events = await progress_events

        if progress_events:
          _, log_message = progress_events[-1]
          task.progress = log_message[PROGRESS_LOG_KEY]

    return TaskManifest(tasks=self._tasks)

  def task_id(self, name: str, description: Optional[str] = None) -> TaskId:
    """Create a unique ID for a task."""
    task_id = uuid.uuid4().bytes.hex()
    self._tasks[task_id] = TaskInfo(
      name=name,
      status=TaskStatus.PENDING,
      progress=None,
      description=description,
      start_timestamp=datetime.now().isoformat())
    return task_id

  def _set_task_completed(self, task_id: TaskId, task_future: Future) -> None:
    if task_future.status == 'error':
      self._tasks[task_id].status = TaskStatus.ERROR
      tb = traceback.format_tb(task_future.traceback())
      e = task_future.exception()
      self._tasks[task_id].error = f'{e}: \n{tb}'
      raise e
    else:
      self._tasks[task_id].status = TaskStatus.COMPLETED
      self._tasks[task_id].progress = 1.0

    end_timestamp = datetime.now().isoformat()
    self._tasks[task_id].end_timestamp = end_timestamp

    elapsed = datetime.fromisoformat(end_timestamp) - datetime.fromisoformat(
      self._tasks[task_id].start_timestamp)
    log(f'Task completed "{task_id}": "{self._tasks[task_id].name}" in '
        f'{_pretty_timedelta(elapsed)}.')

  def execute(self, task_id: str, task: Task, *args: Any) -> None:
    """Create a unique ID for a task."""
    log(f'Scheduling task "{task_id}": "{self._tasks[task_id].name}".')

    task_future = self._dask_client.submit(task, *args, key=task_id)
    task_future.add_done_callback(
      lambda task_future: self._set_task_completed(task_id, task_future))

  async def stop(self) -> None:
    """Stop the task manager and close the dask client."""
    await self._dask_client.close()


@functools.cache
def task_manager() -> TaskManager:
  """The global singleton for the task manager."""
  return TaskManager()


def _progress_event_topic(task_id: TaskId) -> Variable:
  return f'{task_id}_progress'


TProgress = TypeVar('TProgress')


def progress(it: Iterable[TProgress],
             task_id: Optional[TaskId],
             estimated_len: int,
             emit_every_frac: float = .01) -> Iterable[TProgress]:
  """An iterable wrapper that emits progress and yields the original iterable."""
  if not task_id:
    yield from it
    return

  estimated_len = max(1, estimated_len)

  emit_every = int(estimated_len * emit_every_frac)
  emit_every = max(1, emit_every)

  it_idx = 0
  for t in it:
    if it_idx % emit_every == 0:
      set_worker_task_progress(task_id, float(it_idx / estimated_len))
    it_idx += 1
    yield t

  set_worker_task_progress(task_id, 1.0)


def set_worker_task_progress(task_id: TaskId, progress: float) -> None:
  """Updates a task with a progress between 0 and 1.

  This method does not exist on the TaskManager as it is meant to be a standalone method used by
  workers running tasks on separate processes so does not have access to task manager state.
  """
  get_worker().log_event(_progress_event_topic(task_id), {PROGRESS_LOG_KEY: progress})


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
