"""Routing endpoints for running signals on datasets."""
from threading import Thread
from typing import Annotated, Optional

from fastapi import APIRouter, HTTPException
from fastapi.params import Depends
from pydantic import BaseModel, SerializeAsAny, field_validator

from .auth import UserInfo, get_session_user, get_user_access
from .db_manager import get_dataset
from .router_utils import RouteErrorHandler
from .schema import Path
from .signal import Signal, TextEmbeddingSignal, resolve_signal
from .tasks import TaskId, get_task_manager

router = APIRouter(route_class=RouteErrorHandler)


class ComputeSignalOptions(BaseModel):
  """The request for the compute signal endpoint."""

  signal: SerializeAsAny[Signal]

  # The leaf path to compute the signal on.
  leaf_path: Path

  @field_validator('signal', mode='before')
  @classmethod
  def parse_signal(cls, signal: dict) -> Signal:
    """Parse a signal to its specific subclass instance."""
    return resolve_signal(signal)


class ComputeSignalResponse(BaseModel):
  """Response of the compute signal column endpoint."""

  task_id: TaskId


@router.post('/{namespace}/{dataset_name}/compute_signal')
def compute_signal(
  namespace: str,
  dataset_name: str,
  options: ComputeSignalOptions,
  user: Annotated[Optional[UserInfo], Depends(get_session_user)],
) -> ComputeSignalResponse:
  """Compute a signal for a dataset."""
  if not get_user_access(user).dataset.compute_signals:
    raise HTTPException(401, 'User does not have access to compute signals over this dataset.')

  # Resolve the signal outside the task so we don't look up the signal in the registry. This gets
  # implicitly pickled by the serializer when _task_compute_signal is pickled.
  # NOTE: This unfortunately does not work in Jupyter because a module is not picklable. In this
  # case, we recommend defining and registering the signal outside a Jupyter notebook.
  signal = options.signal

  path_str = '.'.join(map(str, options.leaf_path))
  task_id = get_task_manager().task_id(
    name=f'[{namespace}/{dataset_name}] Compute signal "{options.signal.name}" on "{path_str}"',
    description=f'Config: {options.signal}',
  )

  dataset = get_dataset(namespace, dataset_name)

  def run() -> None:
    dataset.compute_signal(
      signal,
      options.leaf_path,
      # Overwrite for text embeddings since we don't have UI to control deleting embeddings.
      overwrite=isinstance(options.signal, TextEmbeddingSignal),
      task_id=task_id,
      remote=signal.remote,
    )

  thread = Thread(target=run, daemon=True)
  thread.start()

  return ComputeSignalResponse(task_id=task_id)


class ClusterOptions(BaseModel):
  """The request for the cluster endpoint."""

  input: Path
  output_path: Optional[Path] = None
  remote: bool = False
  overwrite: bool = False


class ClusterResponse(BaseModel):
  """Response of the cluster endpoint."""

  task_id: TaskId


@router.post('/{namespace}/{dataset_name}/cluster')
def cluster(
  namespace: str,
  dataset_name: str,
  options: ClusterOptions,
  user: Annotated[Optional[UserInfo], Depends(get_session_user)],
) -> ClusterResponse:
  """Compute clusters over an input path."""
  if not get_user_access(user).dataset.compute_signals:
    raise HTTPException(401, 'User does not have access to compute clusters over this dataset.')

  path_str = '.'.join(map(str, options.input))
  task_name = f'[{namespace}/{dataset_name}] Clustering "{path_str}"'
  task_id = get_task_manager().task_id(name=task_name)
  dataset = get_dataset(namespace, dataset_name)

  def run() -> None:
    dataset.cluster(
      options.input,
      options.output_path,
      remote=options.remote,
      overwrite=options.overwrite,
      task_id=task_id,
    )

  thread = Thread(target=run, daemon=True)
  thread.start()
  return ClusterResponse(task_id=task_id)


class DeleteSignalOptions(BaseModel):
  """The request for the delete signal endpoint."""

  # The signal path holding the data from the signal.
  signal_path: Path


class DeleteSignalResponse(BaseModel):
  """Response of the compute signal column endpoint."""

  completed: bool


@router.delete('/{namespace}/{dataset_name}/delete_signal')
def delete_signal(
  namespace: str,
  dataset_name: str,
  options: DeleteSignalOptions,
  user: Annotated[Optional[UserInfo], Depends(get_session_user)],
) -> DeleteSignalResponse:
  """Delete a signal from a dataset."""
  if not get_user_access(user).dataset.delete_signals:
    raise HTTPException(401, 'User does not have access to delete this signal.')

  dataset = get_dataset(namespace, dataset_name)
  dataset.delete_signal(options.signal_path)
  return DeleteSignalResponse(completed=True)
