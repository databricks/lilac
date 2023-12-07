"""Manage FastAPI background tasks."""

import asyncio
import builtins
import functools
import multiprocessing
import time
import traceback
import uuid
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import datetime, timedelta
from enum import Enum
from types import TracebackType
from typing import (
  Any,
  Awaitable,
  Callable,
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
from distributed import Future as DaskFuture
from distributed import get_client, get_worker, wait
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

# A tuple of the (task_id, step_id).
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
  DATASET_MAP = 'dataset_map'


class TaskStepInfo(BaseModel):
  """Information about a step of the task.."""

  progress: Optional[float] = None
  description: Optional[str] = None

  it_idx: Optional[int] = None
  estimated_len: Optional[int] = None
  estimated_total_sec: Optional[float] = None
  elapsed_sec: Optional[float] = None
  it_per_sec: Optional[float] = None

  # The start time of the task step, from time.time().
  start_time: Optional[float] = None
  # Maps a shard id to the (current, total) progress of the shard. We cannot use a dict here because
  # dask serializes with msgpack which does not support dicts.
  shard_progresses: list[tuple[int, tuple[int, int]]] = []


TaskExecutionType = Literal['processes', 'threads']


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

  # Maps task_ids to their dask futures.
  _dask_futures: dict[str, list[DaskFuture]] = {}
  # Maps thread task_ids to their futures.
  _thread_futures: dict[str, list[Future]] = {}

  # Maps a task_id to the count of shard completions.
  _task_shard_completions: dict[str, int] = {}

  _task_threadpools: dict[str, ThreadPoolExecutor] = {}

  def __init__(self, dask_client: Optional[Client] = None) -> None:
    """By default, use a dask multi-processing client.

    A user can pass in a dask client to use a different executor.
    """
    # Set dasks workers to be non-daemonic so they can spawn child processes if they need to. This
    # is particularly useful for signals that use libraries with multiprocessing support.
    dask.config.set({'distributed.worker.daemon': False})

    asynchronous = True
    try:
      asyncio.get_running_loop()
    except RuntimeError as e:
      asynchronous = False

    self.n_workers = multiprocessing.cpu_count()
    total_memory_gb = psutil.virtual_memory().total / (1024**3)
    self._dask_client = dask_client or Client(
      asynchronous=asynchronous,
      memory_limit=f'{total_memory_gb} GB',
      n_workers=self.n_workers,
      processes=True,
    )

  async def _update_tasks(self) -> None:
    adapter = TypeAdapter(list[TaskStepInfo])
    for task_id, task in list(self._tasks.items()):
      if task.status == TaskStatus.COMPLETED:
        if task_id in self._task_threadpools:
          threadpool = self._task_threadpools[task_id]
          threadpool.shutdown()
          # Clean up threaded events.
          del THREADED_EVENTS[_progress_event_topic(task_id)]
        continue

      task_progress_topic = _progress_event_topic(task_id)
      if task_id in self._dask_futures:
        try:
          step_events = cast(Any, self._dask_client.get_events(task_progress_topic))
        except Exception as e:
          return None
        # This allows us to work with both sync and async clients.
        if not isinstance(step_events, tuple):
          step_events = await step_events
      else:
        step_events = cast(Any, get_worker_events(task_progress_topic))

      if step_events:
        _, log_message = step_events[-1]
        steps = adapter.validate_python(log_message[STEPS_LOG_KEY])
        task.steps = steps
        if steps:
          cur_step_id = get_current_step_id(steps)
          cur_step = steps[cur_step_id]
          it_idx = cur_step.it_idx or 0
          estimated_len: int = cur_step.estimated_len or 0
          if cur_step.shard_progresses:
            it_idx = sum([shard_it_idx for _, (shard_it_idx, _) in cur_step.shard_progresses])
            estimated_len = sum([shard_len for _, (_, shard_len) in cur_step.shard_progresses])

          # 1748/1748 [elapsed 00:16<00:00, 106.30 ex/s]
          elapsed = ''
          if cur_step.elapsed_sec:
            elapsed = f'{pretty_timedelta(timedelta(seconds=cur_step.elapsed_sec))}'
            if cur_step.estimated_total_sec:
              # Only show estimated when in progress.
              elapsed = (
                f'{elapsed} < {pretty_timedelta(timedelta(seconds=cur_step.estimated_total_sec))}'
              )

          task.details = (
            f'{it_idx:,}/{estimated_len:,} [{elapsed} {cur_step.it_per_sec:,.2f} ex/s]'
            if it_idx is not None
            and estimated_len is not None
            and cur_step.it_per_sec
            and cur_step.elapsed_sec
            else None
          )

          task.step_progress = cur_step.progress
          task.progress = (sum([step.progress or 0.0 for step in steps])) / len(steps)
          # Don't show an indefinite jump if there are multiple steps.
          if cur_step_id > 0 and task.step_progress is None:
            task.step_progress = 0.0

          task.message = f'Step {cur_step_id+1}/{len(steps)}'
          if cur_step.description:
            task.message += f': {cur_step.description}'
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
    dask_futures: list[DaskFuture] = []
    thread_futures: list[Future] = []
    if task_ids is None:
      task_ids = list(self._dask_futures.keys())
    for task_id in task_ids:
      # task_id isn't in dask_futures when it's a thread task.
      if task_id in self._dask_futures:
        task_futures = self._dask_futures[task_id]
        dask_futures.extend(task_futures)

      if task_id in self._thread_futures:
        task_futures = self._thread_futures[task_id]
        thread_futures.extend(task_futures)

    # Wait for all dask futures.
    if dask_futures:
      wait_result = wait(dask_futures)
      if asyncio.iscoroutine(wait_result):
        asyncio.get_event_loop().run_until_complete(wait_result)

      for future in dask_futures:
        if future.status == 'error':
          task_error = future.exception()
          if asyncio.iscoroutine(task_error):
            task_error = asyncio.get_event_loop().run_until_complete(task_error)
          raise task_error

    # Wait for all thread futures.
    if thread_futures:
      for future in thread_futures:
        future.result()

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

  def _set_task_completed(self, task_id: TaskId, task_future: Union[DaskFuture, Future]) -> None:
    end_timestamp = datetime.now().isoformat()
    self._tasks[task_id].end_timestamp = end_timestamp

    elapsed = datetime.fromisoformat(end_timestamp) - datetime.fromisoformat(
      self._tasks[task_id].start_timestamp
    )
    elapsed_formatted = pretty_timedelta(elapsed)

    if isinstance(task_future, DaskFuture) and task_future.status == 'error':
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

    status = task_future.status if isinstance(task_future, DaskFuture) else 'completed'

    if task_id in self._dask_futures:
      del self._dask_futures[task_id]

  def _set_task_shard_completed(
    self, task_id: TaskId, task_future: Union[DaskFuture, Future], num_shards: int
  ) -> None:
    # Increment task_shard_competions. When the num_shards is reached, set the task as completed.
    self._task_shard_completions[task_id] = self._task_shard_completions.get(task_id, 0) + 1

    if self._task_shard_completions[task_id] == num_shards:
      self._set_task_completed(task_id, task_future)

  def execute(self, task_id: str, type: TaskExecutionType, task: TaskFn, *args: Any) -> None:
    """Execute a task."""
    task_info = self._tasks[task_id]

    if type == 'processes':
      dask_task_id = _dask_task_id(task_id, None)
      task_future = self._dask_client.submit(
        functools.partial(_execute_task, task, task_info, dask_task_id),
        *args,
        key=dask_task_id,
      )
      task_future.add_done_callback(
        lambda task_future: self._set_task_completed(task_id, task_future)
      )
      self._dask_futures[task_id] = [task_future]
    elif type == 'threads':
      if task_id in self._task_threadpools:
        raise ValueError(f'Task {task_id} already exists.')
      self._task_threadpools[task_id] = ThreadPoolExecutor(max_workers=1)
      task_future = self._task_threadpools[task_id].submit(task, *args)

      task_future.add_done_callback(
        lambda task_future: self._set_task_completed(task_id, task_future)
      )

  def execute_sharded(
    self,
    task_id: str,
    type: TaskExecutionType,
    subtasks: list[tuple[TaskFn, list[Any]]],
  ) -> None:
    """Execute a task in multiple shards."""
    if task_id in self._task_threadpools:
      raise ValueError(f'Task {task_id} already exists.')

    task_info = self._tasks[task_id]
    dask_futures: list[DaskFuture] = []
    thread_futures: list[Future] = []

    # Create the threadpool.
    if type == 'threads':
      self._task_threadpools[task_id] = ThreadPoolExecutor(max_workers=len(subtasks))

    for i, (task, args) in enumerate(subtasks):
      if type == 'processes':
        dask_task_id = _dask_task_id(task_id, i)

        task_future = self._dask_client.submit(
          functools.partial(_execute_task, task, task_info, dask_task_id), *args, key=dask_task_id
        )
        task_future.add_done_callback(
          lambda task_future: self._set_task_shard_completed(
            task_id, task_future, num_shards=len(subtasks)
          )
        )
        dask_futures.append(task_future)
      elif type == 'threads':
        task_future = self._task_threadpools[task_id].submit(task, *args)

        task_future.add_done_callback(
          lambda task_future: self._set_task_shard_completed(
            task_id, task_future, num_shards=len(subtasks)
          )
        )
        thread_futures.append(task_future)

    if dask_futures:
      self._dask_futures[task_id] = dask_futures
    if thread_futures:
      self._thread_futures[task_id] = thread_futures

  def stop(self) -> None:
    """Stop the task manager and close the dask client."""
    if self._dask_client.scheduler:
      process_shutdown = self._dask_client.shutdown()
      if asyncio.iscoroutine(process_shutdown):
        asyncio.get_event_loop().run_until_complete(process_shutdown)

  def get_num_workers(self) -> int:
    """Get the number of workers."""
    scheduler_info = self._dask_client.scheduler_info()
    # The scheduler can be delayed with updating the number of workers, so we use number of workers
    # we provide explicitly as a fallback.
    return (
      len(scheduler_info['workers']) if 'workers' in scheduler_info else multiprocessing.cpu_count()
    )


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


def _dask_task_id(task_id: str, shard_id: Optional[int]) -> str:
  """Returns a dask task id."""
  if shard_id is None:
    return task_id
  return f'{task_id}_{shard_id}'


def _execute_task(task: TaskFn, task_info: TaskInfo, dask_task_id: str, *args: Any) -> None:
  annotations = cast(dict, get_worker().state.tasks[dask_task_id].annotations)
  annotations['task_info'] = task_info
  try:
    task(*args)
  except Exception as e:
    # Get traceback and print it.
    tb = traceback.format_exc()
    log(f'Task {dask_task_id} with {task_info} failed: {e}\n{tb}')
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


def _get_task_step_info(task_step_id: TaskStepId) -> tuple[Optional[TaskStepInfo], bool]:
  """Gets the step info, step info, and whether it is complete."""
  task_id, step_id = task_step_id
  task_manifest = asyncio.get_event_loop().run_until_complete(get_task_manager().manifest())
  task_info = task_manifest.tasks[task_id]
  task_is_complete = task_info.status != TaskStatus.PENDING
  steps = task_manifest.tasks[task_id].steps
  if steps is None:
    return None, task_is_complete

  cur_step_id = get_current_step_id(steps)

  step = steps[step_id]
  return (
    step,
    step.progress == 1.0 or task_is_complete or cur_step_id > step_id,
  )


def show_progress(
  task_step_id: TaskStepId, total_len: Optional[int] = None, description: Optional[str] = None
) -> None:
  """Show a tqdm progress bar.

  Args:
    task_step_id: The task step ID.
    total_len: The total length of the progress. This is optional, but nice to avoid jumping of
      progress bars.
    description: The description of the progress bar.
  """
  # Don't show progress bars in unit test to reduce output spam.
  if env('LILAC_TEST', False):
    return

  # Use the task_manager state and tqdm to report progress.
  step_info, is_complete = _get_task_step_info(task_step_id)
  estimated_len = None

  last_it_idx = 0
  with tqdm(total=total_len, desc=description) as pbar:
    while not is_complete:
      step_info, is_complete = _get_task_step_info(task_step_id)

      if step_info:
        shard_progresses_dict = dict(step_info.shard_progresses)
        total_it_idx = sum([shard_it_idx for shard_it_idx, _ in shard_progresses_dict.values()])
        total_shard_len = sum([shard_len for _, shard_len in shard_progresses_dict.values()])

        if total_it_idx and last_it_idx and (total_it_idx != last_it_idx):
          pbar.update(total_it_idx - last_it_idx)
        last_it_idx = total_it_idx if step_info else 0

        # If the user didnt pass a total_len explicitly, update the progress bar when we get new
        # information from shards reporting their lengths.
        if not total_len and total_shard_len != estimated_len:
          estimated_len = total_shard_len
          pbar.total = total_shard_len
          pbar.refresh()

    if is_complete:
      total_len = total_len or estimated_len
      if total_len and pbar.n:
        pbar.update(total_len - pbar.n)


def report_progress(
  it: Union[Iterator[TProgress], Iterable[TProgress]],
  task_step_id: Optional[TaskStepId],
  shard_id: Optional[int] = None,
  initial_id: Optional[int] = None,
  estimated_len: Optional[int] = None,
  step_description: Optional[str] = None,
  emit_every_s: float = 0.25,
) -> Generator[TProgress, None, None]:
  """An iterable wrapper that emits progress and yields the original iterable."""
  if not task_step_id or task_step_id[0] == '':
    yield from it
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

  shard_id = shard_id or 0

  it_idx = initial_id if initial_id else 0
  start_time = time.time()
  last_emit = time.time() - emit_every_s

  for t in it:
    cur_time = time.time()
    if estimated_len and cur_time - last_emit > emit_every_s:
      elapsed_sec = cur_time - start_time
      it_per_sec = ((it_idx or 0) - (initial_id or 0.0)) / elapsed_sec
      set_worker_task_progress(
        task_step_id=task_step_id,
        shard_id=shard_id,
        it_idx=it_idx,
        elapsed_sec=elapsed_sec,
        it_per_sec=it_per_sec or 0.0,
        estimated_total_sec=estimated_len / it_per_sec if it_per_sec else 0,
        estimated_len=estimated_len,
      )
      last_emit = cur_time
    yield t
    it_idx += 1

  total_time = time.time() - start_time
  set_worker_task_progress(
    task_step_id=task_step_id,
    it_idx=estimated_len if estimated_len else it_idx,
    shard_id=shard_id,
    elapsed_sec=total_time,
    it_per_sec=(estimated_len or it_idx) / total_time,
    estimated_total_sec=total_time,
    estimated_len=estimated_len or it_idx,
  )


# These methods wrap the dask events so that we can use them in threads (global state) or in dask
# using dask events.
THREADED_EVENTS: dict[str, list[Any]] = {}


def log_event(topic: str, message: dict[str, Any]) -> None:
  """Logs an event to the dask scheduler."""
  if get_is_dask_worker():
    get_worker().log_event(topic, message)
  else:
    THREADED_EVENTS.setdefault(topic, []).append((datetime.now(), message))


def get_events(topic: str) -> tuple[Any, ...]:
  """Gets the events for a topic from the scheduler."""
  if get_is_dask_worker():
    return cast(Any, get_client().get_events(topic))
  else:
    return tuple(THREADED_EVENTS.get(topic, []))


def get_worker_events(topic: str) -> tuple[Any, ...]:
  """Gets the events for a topic from inside a worker."""
  if get_is_dask_worker():
    return cast(Any, get_client().get_events(topic))
  else:
    return tuple(THREADED_EVENTS.get(topic, []))


def set_worker_steps(task_id: TaskId, steps: list[TaskStepInfo]) -> None:
  """Sets up worker steps. Use to provide task step descriptions before they compute."""
  log_event(_progress_event_topic(task_id), {STEPS_LOG_KEY: [step.model_dump() for step in steps]})


def get_worker_steps(task_id: TaskId) -> list[TaskStepInfo]:
  """Gets the last worker steps."""
  events = get_worker_events(_progress_event_topic(task_id))
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
  shard_id: int,
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
  task_id, step_id = task_step_id
  steps = get_worker_steps(task_id)
  if len(steps) <= step_id:
    raise ValueError(f'No step with idx {step_id} exists. Got steps: {steps}')

  shard_progresses_dict = dict(steps[step_id].shard_progresses)
  shard_progresses_dict[shard_id] = (it_idx, estimated_len)
  steps[step_id].shard_progresses = list(shard_progresses_dict.items())

  # Compute the total progress for all shards.
  total_it_idx = sum([shard_it_idx for shard_it_idx, _ in shard_progresses_dict.values()])
  total_len = sum([shard_len for _, shard_len in shard_progresses_dict.values()]) or 1

  steps[step_id].progress = float(total_it_idx) / total_len

  steps[step_id].it_idx = it_idx
  steps[step_id].estimated_len = estimated_len
  steps[step_id].estimated_total_sec = estimated_total_sec
  steps[step_id].elapsed_sec = elapsed_sec
  steps[step_id].it_per_sec = it_per_sec

  set_worker_steps(task_id, steps)
