"""Manage FastAPI background tasks."""

import builtins
import functools
import multiprocessing
import os
import random
import time
import traceback
import uuid
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from multiprocessing.managers import SyncManager
from time import sleep
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

import nest_asyncio
from loky import get_reusable_executor
from pydantic import BaseModel
from tqdm import tqdm

from .env import env
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


@dataclass
class TaskShardInfo:
  """Information about a shard of a task."""

  current_index: int
  estimated_len: Optional[int]


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

  shards: dict[int, TaskShardInfo] = field(default_factory=dict)

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

  _manager: SyncManager
  _shards_proxy: dict[TaskShardId, TaskShardInfo]
  _tasks: dict[str, TaskInfo]

  # Maps a task_id to their futures.
  _futures: dict[str, list[Future]]

  # Maps a task_id to the count of shard completions.
  _task_shard_completions: dict[str, int]

  # Map a task_id to a thread pool. Each task gets its own thread pool when exec_type is 'threads'.
  thread_pools: dict[str, ThreadPoolExecutor]

  def __init__(self) -> None:
    # Maps a task id to the current progress of that task. Shared across all processes.
    self._manager = multiprocessing.Manager()
    self._shards_proxy = cast(dict[TaskShardId, TaskShardInfo], self._manager.dict())
    self._tasks = {}
    self._futures = {}
    self._task_shard_completions = {}
    self.thread_pools = {}

  def _update_task(self, task_id: TaskId) -> None:
    task = self._tasks[task_id]
    total_progress = 0
    total_len = 0
    for shard_index in task.shards.keys():
      task_shard_id = (task_id, shard_index)
      shard_info = self._shards_proxy.get(task_shard_id)
      if shard_info:
        task.shards[shard_index] = shard_info
        total_progress += shard_info.current_index
        if shard_info.estimated_len:
          total_len += shard_info.estimated_len

    elapsed_sec = (datetime.now() - datetime.fromisoformat(task.start_timestamp)).total_seconds()
    ex_per_sec = total_progress / elapsed_sec if elapsed_sec else 0
    # 1748/1748 [elapsed 00:16<00:00, 106.30 ex/s]
    elapsed = pretty_timedelta(timedelta(seconds=elapsed_sec))
    task.details = f'{total_progress:,}/{total_len:,} [{elapsed} {ex_per_sec:,.2f} ex/s]'
    if total_len:
      task.total_len = total_len
    task.total_progress = total_progress

  def _update_tasks(self) -> None:
    for task_id in list(self._tasks.keys()):
      self._update_task(task_id)

  def get_task_info(self, task_id: TaskId) -> TaskInfo:
    """Get the task info for a task."""
    self._update_task(task_id)
    return self._tasks[task_id]

  def manifest(self) -> TaskManifest:
    """Get all tasks."""
    self._update_tasks()
    tasks_with_progress = [
      (task.total_progress / task.total_len)
      for task in self._tasks.values()
      if task.total_progress and task.total_len and task.status != TaskStatus.COMPLETED
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
    new_task = TaskInfo(
      name=name,
      type=type,
      status=TaskStatus.PENDING,
      description=description,
      start_timestamp=datetime.now().isoformat(),
    )
    self._tasks[task_id] = new_task
    return task_id

  def _set_task_completed(self, task_id: TaskId) -> None:
    end_timestamp = datetime.now().isoformat()
    task = self._tasks[task_id]
    task.end_timestamp = end_timestamp

    self._update_task(task_id)

    elapsed = datetime.fromisoformat(end_timestamp) - datetime.fromisoformat(task.start_timestamp)
    elapsed_formatted = pretty_timedelta(elapsed)

    if task.status != TaskStatus.ERROR:
      task.status = TaskStatus.COMPLETED
      task.message = f'Completed in {elapsed_formatted}'

      # Only delete the task futures if it's not an error. Otherwise, we want to keep the future
      # so that calls to manager.wait() will raise the error.

      if task_id in self._futures:
        del self._futures[task_id]

    if task_id in self._task_shard_completions:
      del self._task_shard_completions[task_id]
    if task_id in self.thread_pools:
      thread_pool = self.thread_pools[task_id]
      thread_pool.shutdown(wait=False)
      del self.thread_pools[task_id]

  def _set_task_shard_completed(
    self, task_id: TaskId, task_future: Future, num_shards: int
  ) -> None:
    # Increment task_shard_competions. When the num_shards is reached, set the task as completed.
    task = self._tasks[task_id]
    exc = task_future.exception()
    if exc:
      task.status = TaskStatus.ERROR
      tb = '\n'.join(traceback.format_tb(exc.__traceback__))
      task.error = f'{exc}:\n{tb}'

    self._task_shard_completions[task_id] = self._task_shard_completions.get(task_id, 0) + 1
    if self._task_shard_completions[task_id] == num_shards:
      self._set_task_completed(task_id)

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
    if task_id not in self._tasks:
      raise ValueError(f'Task {task_id} does not exist. Create it with task_id() first')

    if task_id in self.thread_pools:
      raise ValueError(f'Task {task_id} already exists.')

    task = self._tasks[task_id]
    task.shards = {
      i: TaskShardInfo(current_index=0, estimated_len=None) for i in range(len(subtasks))
    }
    futures: list[Future] = []
    # Create the pool of workers.
    if type == 'threads':
      self.thread_pools[task_id] = ThreadPoolExecutor(max_workers=len(subtasks))

    for shard_id, (task_fn, args) in enumerate(subtasks):
      task_shard_id = (task_id, shard_id)
      worker_fn = functools.partial(_execute_task, task_fn, self._shards_proxy, task_shard_id)
      max_workers = len(subtasks)
      cpu_count = os.cpu_count()
      if cpu_count:
        max_workers = max(max_workers, cpu_count)
      pool = (
        get_reusable_executor(max_workers=max_workers)
        if type == 'processes'
        else self.thread_pools[task_id]
      )
      future = pool.submit(worker_fn, *args)
      future.add_done_callback(
        lambda future: self._set_task_shard_completed(task_id, future, num_shards=len(subtasks))
      )
      futures.append(future)

    self._futures[task_id] = futures

  def stop(self) -> None:
    """Stop the task manager."""
    for pool in self.thread_pools.values():
      pool.shutdown()
    self._manager.shutdown()
    get_reusable_executor().shutdown(wait=True)
    del self._manager
    del self._futures
    del self._tasks
    del self._task_shard_completions
    del self.thread_pools
    global _TASK_MANAGER
    _TASK_MANAGER = None


_TASK_MANAGER: Optional[TaskManager] = None
TASK_SHARD_PROXY: Optional[dict[TaskShardId, TaskShardInfo]] = None


def init_worker(proxy: dict[TaskShardId, TaskShardInfo]) -> None:
  """Initializes the worker."""
  global TASK_SHARD_PROXY
  TASK_SHARD_PROXY = proxy
  # Disable the warning about tokenizer library being forked in another process.
  os.environ['TOKENIZERS_PARALLELISM'] = 'true'


def report_shard_info(task_shard_id: TaskShardId, shard_info: TaskShardInfo) -> None:
  """Reporting the current task shard progress to the central manager."""
  global TASK_SHARD_PROXY
  if TASK_SHARD_PROXY is None:
    raise ValueError('No proxy dict was set.')
  TASK_SHARD_PROXY[task_shard_id] = shard_info


def get_shard_info(task_shard_id: TaskShardId) -> TaskShardInfo:
  """Gets the current task info."""
  if TASK_SHARD_PROXY is None:
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


def show_progress_and_block(task_id: TaskId, description: Optional[str] = None) -> None:
  """Show a tqdm progress bar of a task.

  Args:
    task_id: The task ID.
    description: The description of the progress bar.
  """
  # Don't show progress bars in unit test to reduce output spam.
  task_manager = get_task_manager()
  if env('LILAC_TEST', False):
    task_manager.wait([task_id])
    return

  task_info = task_manager.get_task_info(task_id)
  with tqdm(total=task_info.total_len, desc=description) as pbar:
    while True:
      task_info = task_manager.get_task_info(task_id)
      if task_info.total_len and pbar.total != task_info.total_len:
        pbar.total = task_info.total_len
        pbar.refresh()
      if task_info.total_progress:
        pbar.update(task_info.total_progress - pbar.n)
      if task_info.status == TaskStatus.COMPLETED:
        break
      if task_info.status == TaskStatus.ERROR:
        break
      sleep(0.1)


# The interval to emit progress events.
EMIT_DELAY_PER_WORKER = 0.5
MIN_DELAY = 0.1


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

  shard_info = TaskShardInfo(current_index=initial_index or 0, estimated_len=estimated_len)
  shard_count = shard_count if shard_count else 1
  last_emit = 0.0
  # Reduce the emit frequency if there are multiple shards to reduce IPC.
  max_delay = EMIT_DELAY_PER_WORKER * shard_count
  for t in it:
    shard_info.current_index += 1
    emit_delay = random.uniform(MIN_DELAY, max_delay)
    cur_time = time.time()
    if estimated_len and cur_time - last_emit > emit_delay:
      report_shard_info(task_shard_id, shard_info)
      last_emit = cur_time
    yield t
  report_shard_info(task_shard_id, shard_info)
