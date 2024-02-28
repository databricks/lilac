"""Routing endpoints for running signals on datasets."""
from typing import Annotated, Optional, Union

from fastapi import APIRouter, HTTPException
from fastapi.params import Depends
from pydantic import BaseModel, SerializeAsAny, field_validator
from pydantic import Field as PydanticField

from .auth import UserInfo, get_session_user, get_user_access
from .data.clustering import default_cluster_output_path
from .dataset_format import DatasetFormatInputSelector, get_dataset_format_cls
from .db_manager import get_dataset
from .router_utils import RouteErrorHandler
from .schema import Path, PathTuple, normalize_path
from .signal import Signal, resolve_signal
from .tasks import TaskId, get_task_manager, launch_task

router = APIRouter(route_class=RouteErrorHandler)


class ComputeSignalOptions(BaseModel):
  """The request for the compute signal endpoint."""

  signal: SerializeAsAny[Signal]

  # The leaf path to compute the signal on.
  leaf_path: Path

  overwrite: bool = False
  use_garden: bool = False

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
      overwrite=options.overwrite,
      task_id=task_id,
      use_garden=options.use_garden,
    )

  launch_task(task_id, run)

  return ComputeSignalResponse(task_id=task_id)


class ClusterOptions(BaseModel):
  """The request for the cluster endpoint."""

  input: Optional[Path] = None
  input_selector: Optional[str] = None

  output_path: Optional[Path] = None
  use_garden: bool = PydanticField(
    default=False, description='Accelerate computation by running remotely on Lilac Garden.'
  )
  skip_noisy_assignment: bool = PydanticField(
    default=False,
    description='Skip assignment of noisy points to the nearest cluster to speed up clustering.',
  )

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

  dataset = get_dataset(namespace, dataset_name)
  manifest = dataset.manifest()

  cluster_input: Optional[Union[DatasetFormatInputSelector, PathTuple]] = None
  if options.input:
    path_str = '.'.join(map(str, options.input))
    task_name = f'[{namespace}/{dataset_name}] Clustering "{path_str}"'
    cluster_input = normalize_path(options.input)
  elif options.input_selector:
    dataset_format = manifest.dataset_format
    if dataset_format is None:
      raise ValueError('Dataset format is not defined.')

    format_cls = get_dataset_format_cls(dataset_format.name)
    if format_cls is None:
      raise ValueError(f'Unknown format: {dataset_format.name}')

    cluster_input = format_cls.input_selectors[options.input_selector]

    task_name = (
      f'[{namespace}/{dataset_name}] Clustering using input selector ' f'"{options.input_selector}"'
    )
  else:
    raise HTTPException(400, 'Either input or input_selector must be provided.')

  task_id = get_task_manager().task_id(name=task_name)

  def run() -> None:
    dataset.cluster(
      cluster_input,
      options.output_path,
      use_garden=options.use_garden,
      overwrite=options.overwrite,
      task_id=task_id,
      skip_noisy_assignment=options.skip_noisy_assignment,
    )

  launch_task(task_id, run)
  return ClusterResponse(task_id=task_id)


class DefaultClusterOutputPathOptions(BaseModel):
  """Request body for the default cluster output path endpoint."""

  input_path: Path


@router.post('/{namespace}/{dataset_name}/default_cluster_output_path')
def get_default_cluster_output_path(options: DefaultClusterOutputPathOptions) -> Path:
  """Get format selectors for the dataset if a format has been inferred."""
  return default_cluster_output_path(options.input_path)


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
