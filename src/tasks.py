"""Manage FastAPI background tasks."""

import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel

TaskId = str


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


class TaskManager(BaseModel):
  """Manage FastAPI background tasks."""
  tasks: dict[str, TaskInfo] = {}

  def task_id(self, name: str, description: Optional[str] = None) -> TaskId:
    """Create a unique ID for a task."""
    task_id = uuid.uuid4().bytes.hex()
    self.tasks[task_id] = TaskInfo(name=name,
                                   status=TaskStatus.PENDING,
                                   progress=None,
                                   description=description,
                                   start_timestamp=datetime.now().isoformat())
    return task_id

  def update_task(self,
                  task_id: TaskId,
                  status: TaskStatus,
                  progress: Optional[float] = None) -> None:
    """Updates a task with a status and a progress between 0 and 1."""
    if task_id not in self.tasks:
      raise ValueError('Unknown task ID', task_id)

    self.tasks[task_id].status = status
    if status == TaskStatus.COMPLETED:
      self.tasks[task_id].progress = 1.0
      self.tasks[task_id].end_timestamp = datetime.now().isoformat()
    else:
      self.tasks[task_id].progress = progress


TASK_MANAGER = TaskManager()
