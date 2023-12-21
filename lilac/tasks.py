"""Manage FastAPI background tasks."""

import uuid
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import (
  Any,
  Awaitable,
  Callable,
  Iterator,
  Literal,
  Optional,
  TypeVar,
  Union,
)

from pydantic import BaseModel
from tqdm import tqdm

from .env import env
from .utils import pretty_timedelta

# A tuple of the (task_id, shard_id).
TaskId = str
TaskShardId = tuple[TaskId, int]
TaskFn = Union[Callable[..., Any], Callable[..., Awaitable[Any]]]


class TaskStatus(str, Enum):
  """Enum holding a tasks status."""

  PENDING = 'pending'
  COMPLETED = 'completed'
  ERROR = 'error'


class TaskType(str, Enum):
  """Enum holding a task type."""

  DATASET_LOAD = 'dataset_load'
  DATASET_MAP = 'dataset_map'


TaskExecutionType = Literal['processes', 'threads']


@dataclass
class TaskInfo:
  """Metadata about a task."""

  name: str
  start_timestamp: str
  status: TaskStatus
  end_timestamp: Optional[str] = None
  type: Optional[TaskType] = None
  message: Optional[str] = None
  details: Optional[str] = None

  description: Optional[str] = None
  error: Optional[str] = None

  total_len: Optional[int] = None
  total_progress: Optional[int] = None


class TaskManifest(BaseModel):
  """Information for tasks that are running or completed."""

  tasks: dict[str, TaskInfo]
  progress: Optional[float] = None


class TaskManager:
  """Manage FastAPI background tasks."""

  _tasks: dict[TaskId, TaskInfo]

  def __init__(self) -> None:
    # Maps a task id to the current progress of that task. Shared across all processes.
    self._tasks = {}

  def get_task_info(self, task_id: TaskId) -> TaskInfo:
    """Get the task info for a task."""
    return self._tasks[task_id]

  def manifest(self) -> TaskManifest:
    """Get all tasks."""
    tasks_with_progress = [
      (task.total_progress / task.total_len)
      for task in self._tasks.values()
      if task.total_progress and task.total_len and task.status != TaskStatus.COMPLETED
    ]
    return TaskManifest(
      tasks=self._tasks,
      progress=sum(tasks_with_progress) / len(tasks_with_progress) if tasks_with_progress else None,
    )

  def task_id(
    self,
    name: str,
    type: Optional[TaskType] = None,
    description: Optional[str] = None,
    total_len: Optional[int] = None,
  ) -> TaskId:
    """Create a unique ID for a task."""
    task_id = uuid.uuid4().hex
    new_task = TaskInfo(
      name=name,
      type=type,
      status=TaskStatus.PENDING,
      description=description,
      start_timestamp=datetime.now().isoformat(),
      total_len=total_len,
    )
    self._tasks[task_id] = new_task
    return task_id

  def report_task_progress(self, task_id: TaskId, progress: int) -> None:
    """Report the progress of a task."""
    task = self._tasks[task_id]
    task.total_progress = progress

  def set_task_completed(self, task_id: TaskId) -> None:
    """Mark a task completed."""
    end_timestamp = datetime.now().isoformat()
    task = self._tasks[task_id]
    task.end_timestamp = end_timestamp

    elapsed = datetime.fromisoformat(end_timestamp) - datetime.fromisoformat(task.start_timestamp)
    elapsed_formatted = pretty_timedelta(elapsed)

    if task.status != TaskStatus.ERROR:
      task.status = TaskStatus.COMPLETED
      task.message = f'Completed in {elapsed_formatted}'


_TASK_MANAGER: Optional[TaskManager] = None


def get_task_manager() -> TaskManager:
  """The global singleton for the task manager."""
  global _TASK_MANAGER
  if not _TASK_MANAGER:
    _TASK_MANAGER = TaskManager()
  return _TASK_MANAGER


TProgress = TypeVar('TProgress')


def get_progress_bar(
  task_id: Optional[TaskId] = None,
  task_name: Optional[str] = None,
  task_description: Optional[str] = None,
  task_type: Optional[TaskType] = None,
  estimated_len: Optional[int] = None,
  offset: Optional[int] = None,
) -> Callable[[Iterator[TProgress]], Iterator[TProgress]]:
  """An iterable wrapper that emits progress and yields the original iterable."""
  task_manager = get_task_manager()
  if task_id is None:
    task_name = task_name or ''
    task_id = task_manager.task_id(
      task_name, type=task_type, description=task_description, total_len=estimated_len
    )
  task_info = task_manager.get_task_info(task_id)

  def progress_reporter(it: Iterator[TProgress]) -> Iterator[TProgress]:
    # reduce unit test spam
    if env('LILAC_TEST', False):
      yield from it
      return

    progress = offset or 0
    for item in tqdm(it, total=task_info.total_len, desc=task_info.description):
      progress += 1
      yield item
      task_manager.report_task_progress(task_id, progress)
    task_manager.set_task_completed(task_id)

  return progress_reporter
