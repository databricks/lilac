"""Manage FastAPI background tasks."""

from typing import Any, Callable

from fastapi import BackgroundTasks


class TaskManager():
  """Manage FastAPI background tasks."""

  def add_task(self, task: Callable[[Any], Any], background_tasks: BackgroundTasks) -> None:
    """Add a task to the queue."""
    pass
