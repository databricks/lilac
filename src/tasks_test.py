"""Test the task manager."""

import time

import pytest
from distributed import Client, Event, Future, wait

from .tasks import (
  TaskInfo,
  TaskManager,
  TaskManifest,
  TaskStatus,
  set_worker_task_progress,
)


@pytest.fixture(scope='session')
def test_client() -> Client:
  return Client(processes=False)


async def test_task_manager(test_client: Client) -> None:
  task_manager = TaskManager(test_client)

  # Test that the task manager can create a task.
  task_id = task_manager.task_id(name='test_task', description='test_description')

  # Test the initial manifest.
  manifest = await task_manager.manifest()
  assert manifest == TaskManifest(
    tasks={
      task_id: TaskInfo(
        name='test_task',
        status=TaskStatus.PENDING,
        progress=None,
        description='test_description',
        start_timestamp=manifest.tasks[task_id].start_timestamp,
        end_timestamp=None,
      )
    })

  test_progresses = [0.0, 0.4, 1.0]

  def _test_task() -> None:
    Event('start').wait()
    Event('started').set()

    for i in range(len(test_progresses)):
      Event(f'send-progress-{i}').wait()
      set_worker_task_progress(task_id, test_progresses[i])
      Event(f'recv-progress-{i}').set()

    Event('end').wait()
    Event('ended').set()

  task_manager.execute(task_id, _test_task)

  # Start the task. We are using events to synchronize the testing code and the task to iteratively
  # advance the progress.
  Event('start').set()
  Event('started').wait()

  for i in range(len(test_progresses)):
    Event(f'send-progress-{i}').set()
    Event(f'recv-progress-{i}').wait()

    # The logging events through the scheduler are not guaranteed to be timed with the events, so we
    # implement a simple retry mechanism to check the progress here and timeout after .2 seconds.
    start = time.time()
    timeout = .2
    while not ((await task_manager.manifest()).tasks[task_id].progress
               == test_progresses[i]) and time.time() - start < timeout:
      time.sleep(.01)

    manifest = await task_manager.manifest()
    assert manifest == TaskManifest(
      tasks={
        task_id: TaskInfo(
          name='test_task',
          status=TaskStatus.PENDING,
          progress=test_progresses[i],
          description='test_description',
          start_timestamp=manifest.tasks[task_id].start_timestamp,
          end_timestamp=None,
        )
      })
  Event('end').set()
  Event('ended').wait()

  wait(Future(task_id))
  # We do not need to retry here because this happens in the main loop.
  manifest = await task_manager.manifest()
  assert manifest == TaskManifest(
    tasks={
      task_id: TaskInfo(
        name='test_task',
        status=TaskStatus.COMPLETED,
        progress=1.0,
        description='test_description',
        start_timestamp=manifest.tasks[task_id].start_timestamp,
        end_timestamp=manifest.tasks[task_id].end_timestamp,
      )
    })

  test_client.close()
