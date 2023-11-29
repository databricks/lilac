"""Tests for tasks.py."""


from .tasks import TaskManager


async def test_task_manager_outside_event_loop() -> None:
  # Make sure we can make a default TaskManager from outside a running loop.
  task_manager = TaskManager()
  assert task_manager is not None
  await task_manager.stop()
