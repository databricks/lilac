"""Test the task manager."""

import pytest
from distributed import Client, Event, Future, wait

from .tasks import TaskInfo, TaskManager, TaskManifest, TaskStatus, set_worker_task_progress


@pytest.fixture(scope='session')
def test_client() -> Client:
  return Client(processes=False)


def test_task_manager(test_client: Client) -> None:
  """Test the task manager."""
  task_manager = TaskManager(test_client)

  # Test that the task manager can create a task.
  task_id = task_manager.task_id(name='test_task', description='test_description')

  # Test the initial manifest.
  manifest = task_manager.manifest()
  assert manifest == TaskManifest(
      tasks={
          task_id:
              TaskInfo(
                  name='test_task',
                  status=TaskStatus.PENDING,
                  progress=0.0,
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

  task_manager.execute(task_id, _test_task)

  # Start the task. We are using events to synchronize the testing code and the task to iteratively
  # advance the progress.
  Event('start').set()
  Event('started').wait()

  for i in range(len(test_progresses)):
    Event(f'send-progress-{i}').set()
    Event(f'recv-progress-{i}').wait()

    manifest = task_manager.manifest()
    assert manifest == TaskManifest(
        tasks={
            task_id:
                TaskInfo(
                    name='test_task',
                    status=TaskStatus.PENDING,
                    progress=test_progresses[i],
                    description='test_description',
                    start_timestamp=manifest.tasks[task_id].start_timestamp,
                    end_timestamp=None,
                )
        })

  wait(Future(task_id))
  assert manifest == TaskManifest(
      tasks={
          task_id:
              TaskInfo(
                  name='test_task',
                  status=TaskStatus.COMPLETED,
                  progress=1.0,
                  description='test_description',
                  start_timestamp=manifest.tasks[task_id].start_timestamp,
                  end_timestamp=manifest.tasks[task_id].end_timestamp,
              )
      })
