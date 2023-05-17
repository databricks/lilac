"""Router for the dataset database."""
import os
from typing import Any, Optional, Sequence, Union, cast

from fastapi import APIRouter, Response
from fastapi.responses import ORJSONResponse
from pydantic import BaseModel, StrictStr, validator

from .config import data_path
from .data.dataset import BinaryOp, Bins, Column, DatasetManifest, FeatureListValue, FeatureValue
from .data.dataset import Filter as PyFilter
from .data.dataset import (
  GroupsSortBy,
  ListOp,
  SelectRowsSchemaResult,
  SortOrder,
  StatsResult,
  UnaryOp,
)
from .db_manager import get_dataset
from .router_utils import RouteErrorHandler
from .schema import PathTuple, normalize_path
from .signals.default_signals import register_default_signals
from .signals.signal import Signal, resolve_signal
from .tasks import TaskId, task_manager
from .utils import DATASETS_DIR_NAME

router = APIRouter(route_class=RouteErrorHandler)

register_default_signals()


class DatasetInfo(BaseModel):
  """Information about a dataset."""
  namespace: str
  dataset_name: str
  description: Optional[str]


@router.get('/', response_model_exclude_none=True)
def get_datasets() -> list[DatasetInfo]:
  """List the datasets."""
  datasets_path = os.path.join(data_path(), DATASETS_DIR_NAME)
  # Skip if 'datasets' doesn't exist.
  if not os.path.isdir(datasets_path):
    return []

  dataset_infos: list[DatasetInfo] = []
  for namespace in os.listdir(datasets_path):
    dataset_dir = os.path.join(datasets_path, namespace)
    # Skip if namespace is not a directory.
    if not os.path.isdir(dataset_dir):
      continue
    if namespace.startswith('.'):
      continue

    for dataset_name in os.listdir(dataset_dir):
      # Skip if dataset_name is not a directory.
      dataset_path = os.path.join(dataset_dir, dataset_name)
      if not os.path.isdir(dataset_path):
        continue
      if dataset_name.startswith('.'):
        continue

      dataset_infos.append(DatasetInfo(namespace=namespace, dataset_name=dataset_name))

  return dataset_infos


class WebManifest(BaseModel):
  """Information about a dataset."""
  dataset_manifest: DatasetManifest


@router.get('/{namespace}/{dataset_name}')
def get_manifest(namespace: str, dataset_name: str) -> WebManifest:
  """Get the web manifest for the dataset."""
  dataset = get_dataset(namespace, dataset_name)
  res = WebManifest(dataset_manifest=dataset.manifest())
  # Avoids the error that Signal abstract class is not serializable.
  return cast(WebManifest, ORJSONResponse(res.dict(exclude_none=True)))


class ComputeSignalOptions(BaseModel):
  """The request for the compute signal endpoint."""
  signal: Signal

  # The leaf path to compute the signal on.
  leaf_path: PathTuple

  @validator('signal', pre=True)
  def parse_signal(cls, signal: dict) -> Signal:
    """Parse a signal to its specific subclass instance."""
    return resolve_signal(signal)


class ComputeSignalResponse(BaseModel):
  """Response of the compute signal column endpoint."""
  task_id: TaskId


@router.post('/{namespace}/{dataset_name}/compute_signal_column')
def compute_signal_column(namespace: str, dataset_name: str,
                          options: ComputeSignalOptions) -> ComputeSignalResponse:
  """Compute a signal for a dataset."""

  def _task_compute_signal(namespace: str, dataset_name: str, options_dict: dict,
                           task_id: TaskId) -> None:
    # NOTE: We manually call .dict() to avoid the dask serializer, which doesn't call the underlying
    # pydantic serializer.
    options = ComputeSignalOptions(**options_dict)
    dataset = get_dataset(namespace, dataset_name)
    dataset.compute_signal(options.signal, options.leaf_path, task_id=task_id)

  path_str = '.'.join(map(str, options.leaf_path))
  task_id = task_manager().task_id(
    name=f'Compute signal "{options.signal.name}" on "{path_str}" '
    f'in dataset "{namespace}/{dataset_name}"',
    description=f'Config: {options.signal}')
  task_manager().execute(task_id, _task_compute_signal, namespace, dataset_name, options.dict(),
                         task_id)

  return ComputeSignalResponse(task_id=task_id)


class GetStatsOptions(BaseModel):
  """The request for the get stats endpoint."""
  leaf_path: PathTuple


@router.post('/{namespace}/{dataset_name}/stats')
def get_stats(namespace: str, dataset_name: str, options: GetStatsOptions) -> StatsResult:
  """Get the stats for the dataset."""
  dataset = get_dataset(namespace, dataset_name)
  return dataset.stats(options.leaf_path)


PathREST = Union[tuple[StrictStr, ...], StrictStr]


class BinaryFilter(BaseModel):
  """A filter on a column."""
  path: PathREST
  op: BinaryOp
  value: FeatureValue


class UnaryFilter(BaseModel):
  """A filter on a column."""
  path: PathREST
  op: UnaryOp
  value: None = None


class ListFilter(BaseModel):
  """A filter on a column."""
  path: PathREST
  op: ListOp
  value: FeatureListValue


Filter = Union[BinaryFilter, UnaryFilter, ListFilter]


class SelectRowsOptions(BaseModel):
  """The request for the select rows endpoint."""
  columns: Optional[Sequence[Union[PathREST, Column]]]
  filters: Optional[Sequence[Filter]]
  sort_by: Optional[Sequence[PathREST]]
  sort_order: Optional[SortOrder] = SortOrder.DESC
  limit: Optional[int]
  offset: Optional[int]
  combine_columns: Optional[bool]


class SelectRowsSchemaOptions(BaseModel):
  """The request for the select rows schema endpoint."""
  columns: Optional[Sequence[Union[PathREST, Column]]]
  combine_columns: Optional[bool]


@router.post('/{namespace}/{dataset_name}/select_rows', response_model_exclude_none=True)
def select_rows(namespace: str, dataset_name: str, options: SelectRowsOptions) -> list[dict]:
  """Select rows from the dataset database."""
  dataset = get_dataset(namespace, dataset_name)

  sanitized_filters = [
    PyFilter(path=normalize_path(f.path), op=f.op, value=f.value) for f in (options.filters or [])
  ]
  items = list(
    dataset.select_rows(
      columns=options.columns,
      filters=sanitized_filters,
      sort_by=options.sort_by,
      sort_order=options.sort_order,
      limit=options.limit,
      offset=options.offset,
      combine_columns=options.combine_columns or False))
  return items


@router.post('/{namespace}/{dataset_name}/select_rows_schema', response_model_exclude_none=True)
def select_rows_schema(namespace: str, dataset_name: str,
                       options: SelectRowsSchemaOptions) -> SelectRowsSchemaResult:
  """Select rows from the dataset database."""
  dataset = get_dataset(namespace, dataset_name)
  return dataset.select_rows_schema(
    columns=options.columns, combine_columns=options.combine_columns or False)


class SelectGroupsOptions(BaseModel):
  """The request for the select groups endpoint."""
  leaf_path: PathTuple
  filters: Optional[Sequence[Filter]]
  sort_by: Optional[GroupsSortBy] = GroupsSortBy.COUNT
  sort_order: Optional[SortOrder] = SortOrder.DESC
  limit: Optional[int] = 100
  bins: Optional[Bins]


@router.post('/{namespace}/{dataset_name}/select_groups')
def select_groups(namespace: str, dataset_name: str,
                  options: SelectGroupsOptions) -> list[tuple[Any, int]]:
  """Select groups from the dataset database."""
  dataset = get_dataset(namespace, dataset_name)
  sanitized_filters = [
    PyFilter(path=normalize_path(f.path), op=f.op, value=f.value) for f in (options.filters or [])
  ]
  result = dataset.select_groups(options.leaf_path, sanitized_filters, options.sort_by,
                                 options.sort_order, options.limit, options.bins)
  return list(result)


@router.get('/{namespace}/{dataset_name}/media')
def get_media(namespace: str, dataset_name: str, item_id: str, leaf_path: str) -> Response:
  """Get the media for the dataset."""
  dataset = get_dataset(namespace, dataset_name)
  path = tuple(leaf_path.split('.'))
  result = dataset.media(item_id, path)
  # Return the response via HTTP.
  return Response(content=result.data)
