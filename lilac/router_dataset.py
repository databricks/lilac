"""Router for the dataset database."""
import os
from copy import copy
from typing import Annotated, Any, Literal, Optional, Sequence, Union, cast

from fastapi import APIRouter, HTTPException, Response
from fastapi.params import Depends
from fastapi.responses import FileResponse, ORJSONResponse
from pydantic import BaseModel, Field

from .auth import UserInfo, get_session_user, get_user_access
from .config import DatasetSettings
from .data.dataset import (
  BinaryOp,
  DatasetManifest,
  FeatureListValue,
  FeatureValue,
  GroupsSortBy,
  ListOp,
  PivotResult,
  Search,
  SelectGroupsResult,
  SelectRowsSchemaResult,
  SortOrder,
  StatsResult,
  StringOp,
  UnaryOp,
)
from .data.dataset import Column as DBColumn
from .data.dataset import Filter as PyFilter
from .db_manager import DatasetInfo, get_dataset, list_datasets
from .env import get_project_dir
from .router_utils import RouteErrorHandler
from .schema import Bin, Path, normalize_path
from .signal import Signal, TextEmbeddingSignal, TextSignal
from .signals.concept_labels import ConceptLabelsSignal
from .signals.concept_scorer import ConceptSignal
from .signals.semantic_similarity import SemanticSimilaritySignal
from .signals.substring_search import SubstringSignal
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


@router.delete('/{namespace}/{dataset_name}')
def delete_dataset(
  namespace: str, dataset_name: str, user: Annotated[Optional[UserInfo], Depends(get_session_user)]
) -> None:
  """Delete the dataset."""
  if not get_user_access(user).dataset.delete_dataset:
    raise HTTPException(401, 'User does not have access to delete this dataset.')

  dataset = get_dataset(namespace, dataset_name)
  dataset.delete()


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


class StringFilter(BaseModel):
  """A filter on a column."""

  path: Path
  op: StringOp
  value: str


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


Filter = Union[BinaryFilter, StringFilter, UnaryFilter, ListFilter]

AllSignalTypes = Union[
  ConceptSignal,
  ConceptLabelsSignal,
  SubstringSignal,
  SemanticSimilaritySignal,
  TextEmbeddingSignal,
  TextSignal,
  Signal,
]


# We override the `Column` class so we can add explicitly all signal types for better OpenAPI spec.
class Column(DBColumn):
  """A column in the dataset."""

  signal_udf: Optional[AllSignalTypes] = None


SearchPy = Annotated[Search, Field(discriminator='type')]


class SelectRowsOptions(BaseModel):
  """The request for the select rows endpoint."""

  columns: Sequence[Union[Column, Path]] = []
  searches: Sequence[SearchPy] = []
  filters: Sequence[Filter] = []
  sort_by: Sequence[Path] = []
  sort_order: Optional[SortOrder] = SortOrder.DESC
  limit: Optional[int] = None
  offset: Optional[int] = None
  combine_columns: Optional[bool] = None
  include_deleted: bool = False
  exclude_signals: bool = False


class SelectRowsSchemaOptions(BaseModel):
  """The request for the select rows schema endpoint."""

  columns: Sequence[Union[Path, Column]] = []
  searches: Sequence[SearchPy] = []
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


@router.post('/{namespace}/{dataset_name}/select_rows')
def select_rows(
  namespace: str,
  dataset_name: str,
  options: SelectRowsOptions,
  user: Annotated[Optional[UserInfo], Depends(get_session_user)],
) -> SelectRowsResponse:
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
    include_deleted=options.include_deleted,
    exclude_signals=options.exclude_signals,
    user=user,
  )

  rows = [_exclude_none(row) for row in res]
  return SelectRowsResponse(rows=rows, total_num_rows=res.total_num_rows)


@router.post('/{namespace}/{dataset_name}/select_rows_schema', response_model_exclude_none=True)
def select_rows_schema(
  namespace: str, dataset_name: str, options: SelectRowsSchemaOptions
) -> SelectRowsSchemaResult:
  """Select rows from the dataset database."""
  dataset = get_dataset(namespace, dataset_name)
  return dataset.select_rows_schema(
    columns=options.columns,
    searches=options.searches or [],
    sort_by=options.sort_by,
    sort_order=options.sort_order,
    combine_columns=options.combine_columns or False,
  )


class SelectGroupsOptions(BaseModel):
  """The request for the select groups endpoint."""

  leaf_path: Path
  filters: Sequence[Filter] = []
  searches: Sequence[SearchPy] = []
  sort_by: Optional[GroupsSortBy] = GroupsSortBy.COUNT
  sort_order: Optional[SortOrder] = SortOrder.DESC
  limit: Optional[int] = 100
  bins: Optional[list[Bin]] = None


@router.post('/{namespace}/{dataset_name}/select_groups')
def select_groups(
  namespace: str, dataset_name: str, options: SelectGroupsOptions
) -> SelectGroupsResult:
  """Select groups from the dataset database."""
  dataset = get_dataset(namespace, dataset_name)
  sanitized_filters = [
    PyFilter(path=normalize_path(f.path), op=f.op, value=f.value) for f in (options.filters or [])
  ]
  return dataset.select_groups(
    options.leaf_path,
    sanitized_filters,
    options.sort_by,
    options.sort_order,
    options.limit,
    options.bins,
    searches=options.searches,
  )


class PivotOptions(BaseModel):
  """The request for the pivot endpoint."""

  inner_path: Path
  outer_path: Path
  filters: Sequence[Filter] = []
  searches: Sequence[SearchPy] = []


@router.post('/{namespace}/{dataset_name}/pivot')
def pivot(namespace: str, dataset_name: str, options: PivotOptions) -> PivotResult:
  """REST endpoint for dataset.pivot."""
  dataset = get_dataset(namespace, dataset_name)
  sanitized_filters = [
    PyFilter(path=normalize_path(f.path), op=f.op, value=f.value) for f in (options.filters or [])
  ]
  return dataset.pivot(
    options.outer_path,
    options.inner_path,
    filters=sanitized_filters,
    searches=options.searches,
  )


@router.get('/{namespace}/{dataset_name}/media')
def get_media(namespace: str, dataset_name: str, item_id: str, leaf_path: str) -> Response:
  """Get the media for the dataset."""
  dataset = get_dataset(namespace, dataset_name)
  path = tuple(leaf_path.split('.'))
  result = dataset.media(item_id, path)
  # Return the response via HTTP.
  return Response(content=result.data)


class ExportOptions(BaseModel):
  """The request for the export dataset endpoint."""

  format: Literal['csv', 'json', 'parquet']
  filepath: str
  jsonl: Optional[bool] = False
  columns: Sequence[Path] = []
  include_labels: Sequence[str] = []
  exclude_labels: Sequence[str] = []
  include_signals: bool = False
  # Note: "__deleted__" is "just" another label, and the UI
  # will default to adding the "__deleted__" label to the exclude_labels list. If the user wants
  # to include deleted items, they can remove the "__deleted__" label from the exclude_labels list.
  # This is in contrast to just about every other API endpoint, which does explicitly include a
  # flag for include_deleted.


@router.get('/serve_dataset')
def serve_dataset_file(filepath: str) -> FileResponse:
  """Serve the exported dataset file."""
  filepath = os.path.expanduser(filepath)
  return FileResponse(filepath)


@router.post('/{namespace}/{dataset_name}/export')
def export_dataset(namespace: str, dataset_name: str, options: ExportOptions) -> str:
  """Export the dataset to one of the supported file formats."""
  dataset = get_dataset(namespace, dataset_name)
  # Only create the directory if the filepath has a directory.
  dirname = os.path.dirname(options.filepath)
  if dirname:
    os.makedirs(dirname, exist_ok=True)

  if options.format == 'csv':
    dataset.to_csv(
      filepath=options.filepath,
      columns=options.columns,
      filters=[],
      include_labels=options.include_labels,
      exclude_labels=options.exclude_labels,
      include_signals=options.include_signals,
    )
  elif options.format == 'json':
    dataset.to_json(
      filepath=options.filepath,
      jsonl=options.jsonl or False,
      columns=options.columns,
      filters=[],
      include_labels=options.include_labels,
      exclude_labels=options.exclude_labels,
      include_signals=options.include_signals,
    )
  elif options.format == 'parquet':
    dataset.to_parquet(
      filepath=options.filepath,
      columns=options.columns,
      filters=[],
      include_labels=options.include_labels,
      exclude_labels=options.exclude_labels,
      include_signals=options.include_signals,
    )
  else:
    raise ValueError(f'Unknown format: {options.format}')
  return options.filepath


@router.get('/{namespace}/{dataset_name}/config')
def get_config(
  namespace: str, dataset_name: str, format: Literal['yaml', 'json']
) -> Union[str, dict]:
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
def update_settings(
  namespace: str,
  dataset_name: str,
  settings: DatasetSettings,
  user: Annotated[Optional[UserInfo], Depends(get_session_user)],
) -> None:
  """Update settings for the dataset."""
  if not get_user_access(user).dataset.compute_signals:
    raise HTTPException(401, 'User does not have access to update the settings of this dataset.')

  dataset = get_dataset(namespace, dataset_name)
  dataset.update_settings(settings)
  return None


class AddLabelsOptions(BaseModel):
  """The request for the add labels endpoint."""

  label_name: str
  label_value: Optional[str] = 'true'
  row_ids: Sequence[str] = []
  searches: Sequence[SearchPy] = []
  filters: Sequence[Filter] = []


@router.post('/{namespace}/{dataset_name}/labels', response_model_exclude_none=True)
def add_labels(
  namespace: str,
  dataset_name: str,
  options: AddLabelsOptions,
  user: Annotated[Optional[UserInfo], Depends(get_session_user)],
) -> int:
  """Add a label to the dataset."""
  if not get_user_access(user).dataset.edit_labels:
    raise HTTPException(401, 'User does not have access to add labels to this dataset.')

  if (options.searches or options.filters) and not get_user_access(user).dataset.label_all:
    raise HTTPException(401, 'User does not have access to use the label-all feature.')

  sanitized_filters = [
    PyFilter(path=normalize_path(f.path), op=f.op, value=f.value) for f in (options.filters or [])
  ]

  dataset = get_dataset(namespace, dataset_name)
  if (
    not get_user_access(user).dataset.create_label_type
    and options.label_name not in dataset.get_label_names()
  ):
    raise HTTPException(401, 'User does not have access to create label types in this dataset.')

  return dataset.add_labels(
    name=options.label_name,
    value=options.label_value,
    row_ids=options.row_ids,
    searches=options.searches,
    filters=sanitized_filters,
  )


class RemoveLabelsOptions(BaseModel):
  """The request for the remove labels endpoint."""

  label_name: str
  row_ids: Sequence[str] = []
  searches: Sequence[SearchPy] = []
  filters: Sequence[Filter] = []


@router.delete('/{namespace}/{dataset_name}/labels', response_model_exclude_none=True)
def remove_labels(
  namespace: str,
  dataset_name: str,
  options: RemoveLabelsOptions,
  user: Annotated[Optional[UserInfo], Depends(get_session_user)],
) -> int:
  """Remove a label from the dataset."""
  if not get_user_access(user).dataset.edit_labels:
    raise HTTPException(401, 'User does not have access to remove labels from this dataset.')

  sanitized_filters = [
    PyFilter(path=normalize_path(f.path), op=f.op, value=f.value) for f in (options.filters or [])
  ]

  dataset = get_dataset(namespace, dataset_name)
  return dataset.remove_labels(
    name=options.label_name,
    row_ids=options.row_ids,
    searches=options.searches,
    filters=sanitized_filters,
  )


class DeleteRowsOptions(BaseModel):
  """The request for the delete rows endpoint."""

  row_ids: Sequence[str] = []
  searches: Sequence[SearchPy] = []
  filters: Sequence[Filter] = []


@router.delete('/{namespace}/{dataset_name}/delete_rows', response_model_exclude_none=True)
def delete_rows(
  namespace: str,
  dataset_name: str,
  options: DeleteRowsOptions,
  user: Annotated[Optional[UserInfo], Depends(get_session_user)],
) -> int:
  """Add a label to the dataset."""
  if not get_user_access(user).dataset.delete_rows:
    raise HTTPException(401, 'User does not have access to delete rows on this dataset.')

  sanitized_filters = [
    PyFilter(path=normalize_path(f.path), op=f.op, value=f.value) for f in (options.filters or [])
  ]

  dataset = get_dataset(namespace, dataset_name)
  return dataset.delete_rows(
    row_ids=options.row_ids,
    searches=options.searches,
    filters=sanitized_filters,
  )


class RestoreRowsOptions(BaseModel):
  """The request for the restore rows endpoint."""

  row_ids: Sequence[str] = []
  searches: Sequence[SearchPy] = []
  filters: Sequence[Filter] = []


@router.post('/{namespace}/{dataset_name}/restore_rows', response_model_exclude_none=True)
def restore_rows(
  namespace: str,
  dataset_name: str,
  options: RestoreRowsOptions,
  user: Annotated[Optional[UserInfo], Depends(get_session_user)],
) -> int:
  """Add a label to the dataset."""
  if not get_user_access(user).dataset.delete_rows:
    raise HTTPException(401, 'User does not have access to restore rows on this dataset.')

  sanitized_filters = [
    PyFilter(path=normalize_path(f.path), op=f.op, value=f.value) for f in (options.filters or [])
  ]

  dataset = get_dataset(namespace, dataset_name)
  return dataset.restore_rows(
    row_ids=options.row_ids,
    searches=options.searches,
    filters=sanitized_filters,
  )
