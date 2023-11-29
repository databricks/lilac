"""Tests for tasks.py."""


from .tasks import TaskManager


def test_task_manager_outside_event_loop() -> None:
  # Make sure we can make a default TaskManager from outside a running loop.
  assert TaskManager() is not None
