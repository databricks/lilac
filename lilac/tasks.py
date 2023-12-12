"""Manage FastAPI background tasks."""

import builtins
import functools
import random
import time
import traceback
import uuid
from concurrent.futures import Future, ProcessPoolExecutor, ThreadPoolExecutor
from datetime import datetime, timedelta
from enum import Enum
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
)

import multiprocess
import nest_asyncio
from pydantic import BaseModel

from .utils import log, pretty_timedelta

# nest-asyncio is used to patch asyncio to allow nested event loops. This is required when Lilac is
# run from a Jupyter notebook.
# https://stackoverflow.com/questions/46827007/runtimeerror-this-event-loop-is-already-running-in-python
if hasattr(builtins, '__IPYTHON__'):
  # Check if in an iPython environment, then apply nest_asyncio.
  nest_asyncio.apply()

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


class TaskShardInfo(BaseModel):
  """Information about a shard of a task."""

  current_index: int
  estimated_len: Optional[int]


TaskExecutionType = Literal['processes', 'threads']


class TaskInfo(BaseModel):
  """Metadata about a task."""

  name: str
  type: Optional[TaskType] = None
  status: TaskStatus
  progress: Optional[float] = None
  message: Optional[str] = None
  details: Optional[str] = None

  shards: dict[int, TaskShardInfo] = {}

  description: Optional[str] = None
  start_timestamp: str
  end_timestamp: Optional[str] = None

  error: Optional[str] = None


class TaskManifest(BaseModel):
  """Information for tasks that are running or completed."""

  tasks: dict[str, TaskInfo]
  progress: Optional[float] = None


class TaskManager:
  """Manage FastAPI background tasks."""

  _manager: multiprocess.Manager
  _shards_proxy: dict[TaskShardId, TaskShardInfo]
  _tasks: dict[str, TaskInfo]

  # Maps a task_id to their futures.
  _futures: dict[str, list[Future]] = {}

  # Maps a task_id to the count of shard completions.
  _task_shard_completions: dict[str, int] = {}

  thread_pools: dict[str, ThreadPoolExecutor] = {}
  process_pools: dict[str, ProcessPoolExecutor] = {}

  def __init__(self) -> None:
    # Maps a task id to the current progress of that task. Shared across all processes.
    self._manager = multiprocess.Manager()
    self._shards_proxy = self._manager.dict()

  def _update_tasks(self) -> None:
    for task_id, task in list(self._tasks.items()):
      if task.status == TaskStatus.COMPLETED:
        if task_id in self.thread_pools:
          thread_pool = self.thread_pools[task_id]
          thread_pool.shutdown()
          del self.thread_pools[task_id]
        if task_id in self.process_pools:
          process_pool = self.process_pools[task_id]
          process_pool.shutdown()
          del self.process_pools[task_id]
        continue
      total_progress = 0
      total_count = 0
      for shard_index in task.shards.keys():
        task_shard_id = (task_id, shard_index)
        shard_info = self._shards_proxy.get(task_shard_id)
        if shard_info:
          task.shards[shard_index] = shard_info
          total_progress += shard_info.current_index
          if shard_info.estimated_len:
            total_count += shard_info.estimated_len

      elapsed_sec = (datetime.now() - datetime.fromisoformat(task.start_timestamp)).total_seconds()
      # 1748/1748 [elapsed 00:16<00:00, 106.30 ex/s]
      elapsed = ''
      elapsed = f'{pretty_timedelta(timedelta(seconds=elapsed_sec))}'
      task.details = f'{total_progress:,}/{total_count:,} [{elapsed}]'

      task.progress = total_progress / total_count

  def manifest(self) -> TaskManifest:
    """Get all tasks."""
    self._update_tasks()
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
    futures: list[Future] = []
    if task_ids is None:
      task_ids = list(self._futures.keys())
    for task_id in task_ids:
      if task_id in self._futures:
        future = self._futures[task_id]
        futures.extend(future)

    # Wait for all the futures.
    for f in futures:
      f.result()

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

    if not task_future.done():
      raise ValueError(f'Task {task_id} should be done by now since all sub-tasks have completed.')
    exc = task_future.exception()
    if exc:
      self._tasks[task_id].status = TaskStatus.ERROR
      tb = traceback.format_tb(exc.__traceback__)
      self._tasks[task_id].error = f'{exc}: \n{tb}'
    else:
      self._update_tasks()
      self._tasks[task_id].status = TaskStatus.COMPLETED
      self._tasks[task_id].progress = 1.0
      self._tasks[task_id].message = f'Completed in {elapsed_formatted}'

    if task_id in self._futures:
      del self._futures[task_id]

  def _set_task_shard_completed(
    self, task_id: TaskId, task_future: Future, num_shards: int
  ) -> None:
    # Increment task_shard_competions. When the num_shards is reached, set the task as completed.
    self._task_shard_completions[task_id] = self._task_shard_completions.get(task_id, 0) + 1

    if self._task_shard_completions[task_id] == num_shards:
      self._set_task_completed(task_id, task_future)

  def execute(self, task_id: str, type: TaskExecutionType, task_fn: TaskFn, *args: Any) -> None:
    """Execute a task."""
    return self.execute_sharded(task_id, type, [(task_fn, list(args))])

  def execute_sharded(
    self,
    task_id: str,
    type: TaskExecutionType,
    subtasks: list[tuple[TaskFn, list[Any]]],
  ) -> None:
    """Execute a task in multiple shards."""
    if task_id in self.thread_pools or task_id in self.process_pools:
      raise ValueError(f'Task {task_id} already exists.')

    futures: list[Future] = []
    # Create the pool of workers.
    if type == 'threads':
      self.thread_pools[task_id] = ThreadPoolExecutor(max_workers=len(subtasks))
    elif type == 'processes':
      self.process_pools[task_id] = ProcessPoolExecutor(mp_context=multiprocess.get_context('fork'))
    else:
      raise ValueError(f'Invalid task execution type: {type}')

    for shard_id, (task_fn, args) in enumerate(subtasks):
      step_id = 0
      task_shard_id = (task_id, step_id, shard_id)
      worker_fn = functools.partial(_execute_task, task_fn, self._shards_proxy, task_shard_id)
      pool = self.process_pools[task_id] if type == 'processes' else self.thread_pools[task_id]
      future = pool.submit(worker_fn, *args)
      future.add_done_callback(
        lambda future: self._set_task_shard_completed(task_id, future, num_shards=len(subtasks))
      )
      futures.append(future)

    self._futures[task_id] = futures

  def stop(self) -> None:
    """Stop the task manager and close the dask client."""
    self._manager.shutdown()


_TASK_MANAGER: Optional[TaskManager] = None
TASK_SHARD_PROXY: Optional[dict[TaskShardId, TaskShardInfo]] = None


def init_worker(proxy: dict[TaskShardId, TaskShardInfo]) -> None:
  """Initializes the worker."""
  global TASK_SHARD_PROXY
  TASK_SHARD_PROXY = proxy


def update_shard_info(task_shard_id: TaskShardId, shard_info: TaskShardInfo) -> None:
  """Updates the current task info."""
  global TASK_SHARD_PROXY
  if not TASK_SHARD_PROXY:
    raise ValueError('No proxy dict was set.')
  TASK_SHARD_PROXY[task_shard_id] = shard_info


def get_shard_info(task_shard_id: TaskShardId) -> TaskShardInfo:
  """Gets the current task info."""
  if not TASK_SHARD_PROXY:
    raise ValueError('No proxy dict was set.')
  return TASK_SHARD_PROXY[task_shard_id]


def get_task_manager() -> TaskManager:
  """The global singleton for the task manager."""
  global _TASK_MANAGER
  if _TASK_MANAGER:
    return _TASK_MANAGER
  _TASK_MANAGER = TaskManager()
  return _TASK_MANAGER


def _execute_task(
  task_fn: TaskFn,
  shard_proxy: dict[TaskShardId, TaskShardInfo],
  task_shard_id: TaskShardId,
  *args: Any,
) -> None:
  init_worker(shard_proxy)
  try:
    task_fn(*args)
  except Exception as e:
    # Get traceback and print it.
    tb = traceback.format_exc()
    log(f'Task shard id {task_shard_id} failed: {e}\n{tb}')
    raise e


TProgress = TypeVar('TProgress')


# def show_progress(
#   task_shard_id: TaskShardId, total_len: Optional[int] = None, description: Optional[str] = None
# ) -> None:
#   """Show a tqdm progress bar.

#   Args:
#     task_shard_id: The task step ID.
#     total_len: The total length of the progress. This is optional, but nice to avoid jumping of
#       progress bars.
#     description: The description of the progress bar.
#   """
#   # Don't show progress bars in unit test to reduce output spam.
#   if env('LILAC_TEST', False):
#     return

#   # Use the task_manager state and tqdm to report progress.
#   step_info, is_complete = _get_task_step_info(task_shard_id)
#   estimated_len = None

#   last_it_idx = 0
#   with tqdm(total=total_len, desc=description) as pbar:
#     while not is_complete:
#       step_info, is_complete = _get_task_step_info(task_shard_id)

#       if step_info:
#         shard_progresses_dict = dict(step_info.shard_progresses)
#         total_it_idx = sum([shard_it_idx for shard_it_idx, _ in shard_progresses_dict.values()])
#         total_shard_len = sum([shard_len for _, shard_len in shard_progresses_dict.values()])

#         if total_it_idx and last_it_idx and (total_it_idx != last_it_idx):
#           pbar.update(total_it_idx - last_it_idx)
#         last_it_idx = total_it_idx if step_info else 0

#         # If the user didnt pass a total_len explicitly, update the progress bar when we get new
#         # information from shards reporting their lengths.
#         if not total_len and total_shard_len != estimated_len:
#           estimated_len = total_shard_len
#           pbar.total = total_shard_len
#           pbar.refresh()

#     if is_complete:
#       total_len = total_len or estimated_len
#       if total_len and pbar.n:
#         pbar.update(total_len - pbar.n)


# The interval to emit progress events.
EMIT_EVERY_SEC = 0.5


def report_progress(
  it: Union[Iterator[TProgress], Iterable[TProgress]],
  task_shard_id: Optional[TaskShardId],
  shard_count: Optional[int] = None,
  initial_index: Optional[int] = None,
  estimated_len: Optional[int] = None,
) -> Generator[TProgress, None, None]:
  """An iterable wrapper that emits progress and yields the original iterable."""
  if not task_shard_id or task_shard_id[0] == '':
    yield from it
    return

  it_idx = initial_index if initial_index else 0
  shard_info = TaskShardInfo(current_index=it_idx, estimated_len=estimated_len)
  # Reduce the emit frequency if there are multiple shards to reduce the size of the event stream.
  emit_every_sec = EMIT_EVERY_SEC if not shard_count else EMIT_EVERY_SEC * shard_count
  # Add jitter to the emit frequency to avoid all workers emitting at the same time.
  jitter_sec = random.uniform(0, emit_every_sec)
  last_emit = time.time() - EMIT_EVERY_SEC - jitter_sec

  for t in it:
    cur_time = time.time() + jitter_sec
    if estimated_len and cur_time - last_emit > emit_every_sec:
      shard_info.current_index = it_idx
      update_shard_info(task_shard_id, shard_info)
      last_emit = cur_time
    yield t
    it_idx += 1
