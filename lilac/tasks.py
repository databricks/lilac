"""Manage FastAPI background tasks."""

import asyncio
import builtins
import functools
import multiprocessing
import time
import traceback
import uuid
from datetime import datetime, timedelta
from enum import Enum
from types import TracebackType
from typing import (
  Any,
  Awaitable,
  Callable,
  Coroutine,
  Generator,
  Iterable,
  Iterator,
  Literal,
  Optional,
  TypeVar,
  Union,
  cast,
)

import dask
import nest_asyncio
import psutil
from dask import config as cfg
from dask.distributed import Client
from distributed import Future, get_client, get_worker, wait
from pydantic import BaseModel, TypeAdapter
from tqdm import tqdm

from .env import env
from .utils import log, pretty_timedelta

# nest-asyncio is used to patch asyncio to allow nested event loops. This is required when Lilac is
# run from a Jupyter notebook.
# https://stackoverflow.com/questions/46827007/runtimeerror-this-event-loop-is-already-running-in-python
if hasattr(builtins, '__IPYTHON__'):
  # Check if in an iPython environment, then apply nest_asyncio.
  nest_asyncio.apply()

# Disable the heartbeats of the dask workers to avoid dying after computer goes to sleep.
cfg.set({'distributed.scheduler.worker-ttl': None})

# ID for the step of a task.
TaskStepId = tuple[str, int]
TaskFn = Union[Callable[..., Any], Callable[..., Awaitable[Any]]]
TaskId = str


class TaskStatus(str, Enum):
  """Enum holding a tasks status."""

  PENDING = 'pending'
  COMPLETED = 'completed'
  ERROR = 'error'


class TaskType(str, Enum):
  """Enum holding a task type."""

  DATASET_LOAD = 'dataset_load'


class TaskStepInfo(BaseModel):
  """Information about a step of the task.."""

  progress: Optional[float] = None
  description: Optional[str] = None
  details: Optional[str] = None


class TaskInfo(BaseModel):
  """Metadata about a task."""

  name: str
  type: Optional[TaskType] = None
  status: TaskStatus
  progress: Optional[float] = None
  message: Optional[str] = None
  details: Optional[str] = None
  # The current step's progress.
  step_progress: Optional[float] = None

  # A task may have multiple progress indicators, e.g. for chained signals that compute 3 signals.
  steps: Optional[list[TaskStepInfo]] = None
  description: Optional[str] = None
  start_timestamp: str
  end_timestamp: Optional[str] = None
  error: Optional[str] = None


class TaskManifest(BaseModel):
  """Information for tasks that are running or completed."""

  tasks: dict[str, TaskInfo]
  progress: Optional[float] = None


STEPS_LOG_KEY = 'steps'


class TaskManager:
  """Manage FastAPI background tasks."""

  _tasks: dict[str, TaskInfo] = {}
  # Maps task_ids to their futures.
  _futures: dict[str, Future] = {}

  def __init__(self, dask_client: Optional[Client] = None) -> None:
    """By default, use a dask multi-processing client.

    A user can pass in a dask client to use a different executor.
    """
    # Set dasks workers to be non-daemonic so they can spawn child processes if they need to. This
    # is particularly useful for signals that use libraries with multiprocessing support.
    dask.config.set({'distributed.worker.daemon': False})

    self.n_workers = multiprocessing.cpu_count()
    total_memory_gb = psutil.virtual_memory().total / (1024**3)
    self._dask_client = dask_client or Client(
      asynchronous=not env('LILAC_TEST'),
      memory_limit=f'{total_memory_gb} GB',
      processes=True,
      n_workers=self.n_workers,
    )

  def set_client(self, dask_client: Client) -> None:
    """Sets the dask client."""
    self._dask_client = dask_client

  async def _update_tasks(self) -> None:
    adapter = TypeAdapter(list[TaskStepInfo])
    for task_id, task in list(self._tasks.items()):
      if task.status == TaskStatus.COMPLETED:
        continue

      try:
        step_events = cast(Any, self._dask_client.get_events(_progress_event_topic(task_id)))
      except Exception as e:
        return None

      # This allows us to work with both sync and async clients.
      if not isinstance(step_events, tuple):
        step_events = await step_events

      if step_events:
        _, log_message = step_events[-1]
        steps = adapter.validate_python(log_message[STEPS_LOG_KEY])
        task.steps = steps
        if steps:
          cur_step = get_current_step_id(steps)
          task.details = steps[cur_step].details
          task.step_progress = steps[cur_step].progress
          task.progress = (sum([step.progress or 0.0 for step in steps])) / len(steps)
          # Don't show an indefinite jump if there are multiple steps.
          if cur_step > 0 and task.step_progress is None:
            task.step_progress = 0.0

          task.message = f'Step {cur_step+1}/{len(steps)}'
          if steps[cur_step].description:
            task.message += f': {steps[cur_step].description}'
        else:
          task.progress = None

  async def manifest(self) -> TaskManifest:
    """Get all tasks."""
    await self._update_tasks()
    tasks_with_progress = [
      task.progress
      for task in self._tasks.values()
      if task.progress and task.status != TaskStatus.COMPLETED
    ]
    return TaskManifest(
      tasks=self._tasks,
      progress=sum(tasks_with_progress) / len(tasks_with_progress) if tasks_with_progress else None,
    )

  def wait(self, task_ids: Optional[list[str]] = None) -> None:
    """Wait until all tasks are completed."""
    if task_ids is not None:
      futures = [self._futures[task_id] for task_id in task_ids]
    else:
      futures = list(self._futures.values())

    if futures:
      wait_result = wait(futures)
      if asyncio.iscoroutine(wait_result):
        asyncio.get_event_loop().run_until_complete(wait_result)

    for task_id in task_ids or []:
      future = self._futures[task_id]

      if future.status == 'error':
        task_error = future.exception()
        if asyncio.iscoroutine(task_error):
          task_error = asyncio.get_event_loop().run_until_complete(task_error)
        raise task_error

  def get_task_status(self, task_id: TaskId) -> Literal['pending', 'cancelled', 'finished']:
    """Get the status of a task."""
    future = self._futures[task_id]
    future.traceback
    return cast(Literal['pending', 'cancelled', 'finished'], future.status)

  def task_id(
    self,
    name: str,
    type: Optional[TaskType] = None,
    description: Optional[str] = None,
  ) -> TaskId:
    """Create a unique ID for a task."""
    task_id = uuid.uuid4().hex
    self._tasks[task_id] = TaskInfo(
      name=name,
      type=type,
      status=TaskStatus.PENDING,
      progress=None,
      description=description,
      start_timestamp=datetime.now().isoformat(),
    )
    return task_id

  def _set_task_completed(self, task_id: TaskId, task_future: Future) -> None:
    end_timestamp = datetime.now().isoformat()
    self._tasks[task_id].end_timestamp = end_timestamp

    elapsed = datetime.fromisoformat(end_timestamp) - datetime.fromisoformat(
      self._tasks[task_id].start_timestamp
    )
    elapsed_formatted = pretty_timedelta(elapsed)

    if task_future.status == 'error':
      self._tasks[task_id].status = TaskStatus.ERROR
      e = cast(Exception, task_future.exception())
      tb = traceback.format_tb(cast(TracebackType, task_future.traceback()))
      self._tasks[task_id].error = f'{e}: \n{tb}'
    else:
      # This runs in dask callback thread, so we have to make a new event loop.
      loop = asyncio.new_event_loop()
      loop.run_until_complete(self._update_tasks())
      for step in self._tasks[task_id].steps or []:
        step.progress = 1.0

      self._tasks[task_id].status = TaskStatus.COMPLETED
      self._tasks[task_id].progress = 1.0
      self._tasks[task_id].message = f'Completed in {elapsed_formatted}'

    log(
      f'Task {task_future.status} "{task_id}": "{self._tasks[task_id].name}" in '
      f'{elapsed_formatted}.'
    )

  def execute(self, task_id: str, task: TaskFn, *args: Any) -> None:
    """Execute a task."""
    log(f'Scheduling task "{task_id}": "{self._tasks[task_id].name}".')

    task_info = self._tasks[task_id]
    task_future = self._dask_client.submit(
      functools.partial(_execute_task, task, task_info, task_id), *args, key=task_id
    )
    task_future.add_done_callback(
      lambda task_future: self._set_task_completed(task_id, task_future)
    )

    self._futures[task_id] = task_future

  async def stop(self) -> None:
    """Stop the task manager and close the dask client."""
    await cast(Coroutine, self._dask_client.close())
    self._dask_client.shutdown()

  def get_num_workers(self) -> int:
    """Get the number of workers."""
    return len(self._dask_client.scheduler_info()['workers'])


def get_is_dask_worker() -> bool:
  """Returns True if the current process is a dask worker."""
  try:
    get_worker()
    return True
  except Exception:
    return False


_TASK_MANAGER: Optional[TaskManager] = None


def get_task_manager() -> TaskManager:
  """The global singleton for the task manager."""
  global _TASK_MANAGER
  if _TASK_MANAGER:
    return _TASK_MANAGER
  _TASK_MANAGER = TaskManager()
  return _TASK_MANAGER


def _execute_task(task: TaskFn, task_info: TaskInfo, task_id: str, *args: Any) -> None:
  annotations = cast(dict, get_worker().state.tasks[task_id].annotations)
  annotations['task_info'] = task_info
  try:
    task(*args)
  except Exception as e:
    # Get traceback and print it.
    tb = traceback.format_exc()
    log(f'Task {task_id} with {task_info} failed: {e}\n{tb}')
    raise e


def _progress_event_topic(task_id: TaskId) -> str:
  return f'{task_id}_progress'


TProgress = TypeVar('TProgress')


def get_current_step_id(steps: list[TaskStepInfo]) -> int:
  """Gets the current step."""
  cur_step = 0
  for i, step in enumerate(reversed(steps)):
    if step.progress is not None:
      cur_step = len(steps) - i - 1
      if steps[cur_step].progress == 1.0:
        cur_step = min(cur_step + 1, len(steps) - 1)
      break
  return cur_step


def progress(
  it: Union[Iterator[TProgress], Iterable[TProgress]],
  task_step_id: Optional[TaskStepId],
  initial_id: Optional[int] = None,
  estimated_len: Optional[int] = None,
  step_description: Optional[str] = None,
  emit_every_s: float = 1.0,
) -> Generator[TProgress, None, None]:
  """An iterable wrapper that emits progress and yields the original iterable."""
  if not task_step_id or task_step_id[0] == '':
    yield from tqdm(it, initial=initial_id or 0, desc=step_description, total=estimated_len)
    return

  task_id, step_id = task_step_id
  steps = get_worker_steps(task_id)
  if not steps:
    steps = [TaskStepInfo(description=step_description, progress=0.0)]
  elif len(steps) <= step_id:
    # If the step given exceeds the length of the last step, add a new step.
    steps.append(TaskStepInfo(description=step_description, progress=0.0))
  else:
    steps[step_id].description = step_description
    steps[step_id].progress = 0.0
  set_worker_steps(task_id, steps)

  estimated_len = max(1, estimated_len) if estimated_len else None

  annotations = cast(dict, get_worker().state.tasks[task_id].annotations)
  task_info: TaskInfo = annotations['task_info']

  it_idx = initial_id if initial_id else 0
  start_time = time.time()
  last_emit = time.time() - emit_every_s
  with tqdm(it, initial=it_idx, desc=task_info.name, total=estimated_len) as tq:
    for t in tq:
      cur_time = time.time()
      if estimated_len and cur_time - last_emit > emit_every_s:
        it_per_sec = tq.format_dict['rate'] or 0.0
        set_worker_task_progress(
          task_step_id=task_step_id,
          it_idx=it_idx,
          elapsed_sec=tq.format_dict['elapsed'] or 0.0,
          it_per_sec=it_per_sec or 0.0,
          estimated_total_sec=((estimated_len) / it_per_sec if it_per_sec else 0),
          estimated_len=estimated_len,
        )
        last_emit = cur_time
      yield t
      it_idx += 1

  total_time = time.time() - start_time
  set_worker_task_progress(
    task_step_id=task_step_id,
    it_idx=estimated_len if estimated_len else it_idx,
    elapsed_sec=total_time,
    it_per_sec=(estimated_len or it_idx) / total_time,
    estimated_total_sec=total_time,
    estimated_len=estimated_len or it_idx,
  )


def set_worker_steps(task_id: TaskId, steps: list[TaskStepInfo]) -> None:
  """Sets up worker steps. Use to provide task step descriptions before they compute."""
  get_worker().log_event(
    _progress_event_topic(task_id), {STEPS_LOG_KEY: [step.model_dump() for step in steps]}
  )


def get_worker_steps(task_id: TaskId) -> list[TaskStepInfo]:
  """Gets the last worker steps."""
  events = cast(Any, get_client().get_events(_progress_event_topic(task_id)))
  if not events or not events[-1]:
    return []

  (_, last_event) = events[-1]
  last_info = last_event.get(STEPS_LOG_KEY)
  return [TaskStepInfo(**step_info) for step_info in last_info]


def set_worker_next_step(task_id: TaskId) -> None:
  """Progresses the worker to the next step."""
  steps = get_worker_steps(task_id)
  if steps:
    cur_step = get_current_step_id(steps)
    steps[cur_step].progress = 1.0
    set_worker_steps(task_id, steps)


def set_worker_task_progress(
  task_step_id: TaskStepId,
  it_idx: int,
  elapsed_sec: float,
  it_per_sec: float,
  estimated_total_sec: float,
  estimated_len: int,
) -> None:
  """Updates a task step with a progress between 0 and 1.

  This method does not exist on the TaskManager as it is meant to be a standalone method used by
  workers running tasks on separate processes so does not have access to task manager state.
  """
  progress = float(it_idx) / estimated_len
  task_id, step_id = task_step_id
  steps = get_worker_steps(task_id)
  if len(steps) <= step_id:
    raise ValueError(f'No step with idx {step_id} exists. Got steps: {steps}')
  steps[step_id].progress = progress

  # 1748/1748 [elapsed 00:16<00:00, 106.30 ex/s]
  elapsed = f'{pretty_timedelta(timedelta(seconds=elapsed_sec))}'
  if it_idx != estimated_len:
    # Only show estimated when in progress.
    elapsed = f'{elapsed} < {pretty_timedelta(timedelta(seconds=estimated_total_sec))}'
  steps[step_id].details = f'{it_idx:,}/{estimated_len:,} ' f'[{elapsed}, {it_per_sec:,.2f} ex/s]'

  set_worker_steps(task_id, steps)
