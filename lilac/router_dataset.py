"""Router for the dataset database."""
from copy import copy
from typing import Annotated, Any, Literal, Optional, Sequence, Union, cast
from urllib.parse import unquote

from fastapi import APIRouter, HTTPException, Response
from fastapi.params import Depends
from fastapi.responses import ORJSONResponse
from pydantic import BaseModel, SerializeAsAny, field_validator

from .auth import UserInfo, get_session_user, get_user_access
from .config import DatasetSettings
from .data.dataset import BinaryOp
from .data.dataset import Column as DBColumn
from .data.dataset import DatasetManifest, FeatureListValue, FeatureValue
from .data.dataset import Filter as PyFilter
from .data.dataset import (
  GroupsSortBy,
  ListOp,
  Search,
  SelectGroupsResult,
  SelectRowsSchemaResult,
  SortOrder,
  StatsResult,
  UnaryOp,
)
from .db_manager import DatasetInfo, get_dataset, list_datasets, remove_dataset_from_cache
from .env import get_project_dir
from .router_utils import RouteErrorHandler
from .schema import Bin, Path, normalize_path
from .signal import Signal, TextEmbeddingSignal, TextSignal, resolve_signal
from .signals.concept_labels import ConceptLabelsSignal
from .signals.concept_scorer import ConceptSignal
from .signals.semantic_similarity import SemanticSimilaritySignal
from .signals.substring_search import SubstringSignal
from .tasks import TaskId, get_task_manager
from .utils import to_yaml

router = APIRouter(route_class=RouteErrorHandler)


@router.get('/', response_model_exclude_none=True)
def get_datasets() -> list[DatasetInfo]:
  """List the datasets."""
  return list_datasets(get_project_dir())


class WebManifest(BaseModel):
  """Information about a dataset."""
  dataset_manifest: DatasetManifest


@router.get('/{namespace}/{dataset_name}')
def get_manifest(namespace: str, dataset_name: str) -> WebManifest:
  """Get the web manifest for the dataset."""
  dataset = get_dataset(namespace, dataset_name)
  res = WebManifest(dataset_manifest=dataset.manifest())
  # Avoids the error that Signal abstract class is not serializable.
  return cast(WebManifest, ORJSONResponse(res.model_dump(exclude_none=True)))


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


@router.delete('/{namespace}/{dataset_name}')
def delete_dataset(namespace: str, dataset_name: str) -> None:
  """Delete the dataset."""
  if not get_user_access().dataset.delete_dataset:
    raise HTTPException(401, 'User does not have access to delete this dataset.')

  dataset = get_dataset(namespace, dataset_name)
  dataset.delete()
  remove_dataset_from_cache(namespace, dataset_name)


class ComputeSignalResponse(BaseModel):
  """Response of the compute signal column endpoint."""
  task_id: TaskId


@router.post('/{namespace}/{dataset_name}/compute_signal')
def compute_signal(namespace: str, dataset_name: str,
                   options: ComputeSignalOptions) -> ComputeSignalResponse:
  """Compute a signal for a dataset."""
  if not get_user_access().dataset.compute_signals:
    raise HTTPException(401, 'User does not have access to compute signals over this dataset.')

  def _task_compute_signal(namespace: str, dataset_name: str, options_dict: dict,
                           task_id: TaskId) -> None:
    # NOTE: We manually call .model_dump() to avoid the dask serializer, which doesn't call the
    # underlying pydantic serializer.
    options = ComputeSignalOptions(**options_dict)
    dataset = get_dataset(namespace, dataset_name)
    dataset.compute_signal(options.signal, options.leaf_path, task_step_id=(task_id, 0))

  path_str = '.'.join(map(str, options.leaf_path))
  task_id = get_task_manager().task_id(
    name=f'[{namespace}/{dataset_name}] Compute signal "{options.signal.name}" on "{path_str}"',
    description=f'Config: {options.signal}')
  get_task_manager().execute(task_id, _task_compute_signal, namespace, dataset_name,
                             options.model_dump(), task_id)

  return ComputeSignalResponse(task_id=task_id)


class DeleteSignalOptions(BaseModel):
  """The request for the delete signal endpoint."""
  # The signal path holding the data from the signal.
  signal_path: Path


class DeleteSignalResponse(BaseModel):
  """Response of the compute signal column endpoint."""
  completed: bool


@router.delete('/{namespace}/{dataset_name}/delete_signal')
def delete_signal(namespace: str, dataset_name: str,
                  options: DeleteSignalOptions) -> DeleteSignalResponse:
  """Delete a signal from a dataset."""
  if not get_user_access().dataset.delete_signals:
    raise HTTPException(401, 'User does not have access to delete this signal.')

  dataset = get_dataset(namespace, dataset_name)
  dataset.delete_signal(options.signal_path)
  return DeleteSignalResponse(completed=True)


class GetStatsOptions(BaseModel):
  """The request for the get stats endpoint."""
  leaf_path: Path


@router.post('/{namespace}/{dataset_name}/stats')
def get_stats(namespace: str, dataset_name: str, options: GetStatsOptions) -> StatsResult:
  """Get the stats for the dataset."""
  dataset = get_dataset(namespace, dataset_name)
  return dataset.stats(options.leaf_path)


class BinaryFilter(BaseModel):
  """A filter on a column."""
  path: Path
  op: BinaryOp
  value: FeatureValue


class UnaryFilter(BaseModel):
  """A filter on a column."""
  path: Path
  op: UnaryOp
  value: None = None


class ListFilter(BaseModel):
  """A filter on a column."""
  path: Path
  op: ListOp
  value: FeatureListValue


Filter = Union[BinaryFilter, UnaryFilter, ListFilter]

AllSignalTypes = Union[ConceptSignal, ConceptLabelsSignal, SubstringSignal,
                       SemanticSimilaritySignal, TextEmbeddingSignal, TextSignal, Signal]


# We override the `Column` class so we can add explicitly all signal types for better OpenAPI spec.
class Column(DBColumn):
  """A column in the dataset."""
  signal_udf: Optional[AllSignalTypes] = None


ColumnOrPath = Union[Column, Path]


class SelectRowsOptions(BaseModel):
  """The request for the select rows endpoint."""
  columns: Sequence[Union[Column, Path]] = []
  searches: Sequence[Search] = []
  filters: Sequence[Filter] = []
  sort_by: Sequence[Path] = []
  sort_order: Optional[SortOrder] = SortOrder.DESC
  limit: Optional[int] = None
  offset: Optional[int] = None
  combine_columns: Optional[bool] = None


class SelectRowsSchemaOptions(BaseModel):
  """The request for the select rows schema endpoint."""
  columns: Sequence[Union[Path, Column]] = []
  searches: Sequence[Search] = []
  sort_by: Sequence[Path] = []
  sort_order: Optional[SortOrder] = SortOrder.DESC
  combine_columns: Optional[bool] = None


class SelectRowsResponse(BaseModel):
  """The response for the select rows endpoint."""
  rows: list[dict]
  total_num_rows: int


def _exclude_none(obj: Any) -> Any:
  if isinstance(obj, dict):
    return {k: _exclude_none(v) for k, v in obj.items() if v is not None}
  if isinstance(obj, list):
    return [_exclude_none(v) for v in obj]
  return copy(obj)


# SQL adds {"x": None} for `SELECT x` where x is sparse, thus exclude none to keep response small.
@router.get('/{namespace}/{dataset_name}/select_rows_download')
def select_rows_download(
    namespace: str, dataset_name: str, url_safe_options: str,
    user: Annotated[Optional[UserInfo], Depends(get_session_user)]) -> list[dict]:
  """Select rows from the dataset database and downloads them."""
  options = SelectRowsOptions.model_validate_json(unquote(url_safe_options))

  rows = select_rows(namespace, dataset_name, options, user).rows
  return [_exclude_none(row) for row in rows]


@router.post('/{namespace}/{dataset_name}/select_rows')
def select_rows(
    namespace: str, dataset_name: str, options: SelectRowsOptions,
    user: Annotated[Optional[UserInfo], Depends(get_session_user)]) -> SelectRowsResponse:
  """Select rows from the dataset database."""
  dataset = get_dataset(namespace, dataset_name)

  sanitized_filters = [
    PyFilter(path=normalize_path(f.path), op=f.op, value=f.value) for f in (options.filters or [])
  ]

  res = dataset.select_rows(
    columns=options.columns,
    searches=options.searches or [],
    filters=sanitized_filters,
    sort_by=options.sort_by,
    sort_order=options.sort_order,
    limit=options.limit,
    offset=options.offset,
    combine_columns=options.combine_columns or False,
    user=user)

  rows = [_exclude_none(row) for row in res]
  return SelectRowsResponse(rows=rows, total_num_rows=res.total_num_rows)


@router.post('/{namespace}/{dataset_name}/select_rows_schema', response_model_exclude_none=True)
def select_rows_schema(namespace: str, dataset_name: str,
                       options: SelectRowsSchemaOptions) -> SelectRowsSchemaResult:
  """Select rows from the dataset database."""
  dataset = get_dataset(namespace, dataset_name)
  return dataset.select_rows_schema(
    columns=options.columns,
    searches=options.searches or [],
    sort_by=options.sort_by,
    sort_order=options.sort_order,
    combine_columns=options.combine_columns or False)


class SelectGroupsOptions(BaseModel):
  """The request for the select groups endpoint."""
  leaf_path: Path
  filters: Sequence[Filter] = []
  sort_by: Optional[GroupsSortBy] = GroupsSortBy.COUNT
  sort_order: Optional[SortOrder] = SortOrder.DESC
  limit: Optional[int] = 100
  bins: Optional[list[Bin]] = None


@router.post('/{namespace}/{dataset_name}/select_groups')
def select_groups(namespace: str, dataset_name: str,
                  options: SelectGroupsOptions) -> SelectGroupsResult:
  """Select groups from the dataset database."""
  dataset = get_dataset(namespace, dataset_name)
  sanitized_filters = [
    PyFilter(path=normalize_path(f.path), op=f.op, value=f.value) for f in (options.filters or [])
  ]
  return dataset.select_groups(options.leaf_path, sanitized_filters, options.sort_by,
                               options.sort_order, options.limit, options.bins)


@router.get('/{namespace}/{dataset_name}/media')
def get_media(namespace: str, dataset_name: str, item_id: str, leaf_path: str) -> Response:
  """Get the media for the dataset."""
  dataset = get_dataset(namespace, dataset_name)
  path = tuple(leaf_path.split('.'))
  result = dataset.media(item_id, path)
  # Return the response via HTTP.
  return Response(content=result.data)


@router.get('/{namespace}/{dataset_name}/config')
def get_config(namespace: str, dataset_name: str, format: Literal['yaml',
                                                                  'json']) -> Union[str, dict]:
  """Get the config for the dataset."""
  dataset = get_dataset(namespace, dataset_name)
  config_dict = dataset.config().model_dump(exclude_defaults=True, exclude_none=True)
  if format == 'yaml':
    return to_yaml(config_dict)
  return config_dict


@router.get('/{namespace}/{dataset_name}/settings')
def get_settings(namespace: str, dataset_name: str) -> DatasetSettings:
  """Get the settings for the dataset."""
  dataset = get_dataset(namespace, dataset_name)
  return dataset.settings()


@router.post('/{namespace}/{dataset_name}/settings', response_model_exclude_none=True)
def update_settings(namespace: str, dataset_name: str, settings: DatasetSettings) -> None:
  """Update settings for the dataset."""
  if not get_user_access().dataset.compute_signals:
    raise HTTPException(401, 'User does not have access to update the settings of this dataset.')

  dataset = get_dataset(namespace, dataset_name)
  dataset.update_settings(settings)
  return None


class AddLabelsOptions(BaseModel):
  """The request for the add labels endpoint."""
  label_name: str
  label_value: Optional[str] = 'true'
  row_ids: Sequence[str] = []
  searches: Sequence[Search] = []
  filters: Sequence[Filter] = []


@router.post('/{namespace}/{dataset_name}/labels', response_model_exclude_none=True)
def add_labels(namespace: str, dataset_name: str, options: AddLabelsOptions) -> None:
  """"Add a label to the dataset."""
  if not get_user_access().dataset.edit_labels:
    raise HTTPException(401, 'User does not have access to add labels to this dataset.')

  sanitized_filters = [
    PyFilter(path=normalize_path(f.path), op=f.op, value=f.value) for f in (options.filters or [])
  ]

  dataset = get_dataset(namespace, dataset_name)
  dataset.add_labels(
    name=options.label_name,
    value=options.label_value,
    row_ids=options.row_ids,
    searches=options.searches,
    filters=sanitized_filters)


class RemoveLabelsOptions(BaseModel):
  """The request for the remove labels endpoint."""
  label_name: str
  row_ids: Sequence[str] = []
  searches: Sequence[Search] = []
  filters: Sequence[Filter] = []


@router.delete('/{namespace}/{dataset_name}/labels', response_model_exclude_none=True)
def remove_labels(namespace: str, dataset_name: str, options: RemoveLabelsOptions) -> None:
  """"Add a label to the dataset."""
  if not get_user_access().dataset.edit_labels:
    raise HTTPException(401, 'User does not have access to remove labels from this dataset.')

  sanitized_filters = [
    PyFilter(path=normalize_path(f.path), op=f.op, value=f.value) for f in (options.filters or [])
  ]

  dataset = get_dataset(namespace, dataset_name)
  dataset.remove_labels(
    name=options.label_name,
    row_ids=options.row_ids,
    searches=options.searches,
    filters=sanitized_filters)
