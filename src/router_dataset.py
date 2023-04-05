"""Router for the dataset database."""
import os
from typing import Optional

from fastapi import APIRouter, Response
from pydantic import BaseModel, validator

from .constants import data_path
from .datasets.db_dataset import (
    Bins,
    ColumnId,
    DatasetManifest,
    Filter,
    GroupsSortBy,
    SortOrder,
    StatsResult,
)
from .db_manager import get_dataset_db
from .embeddings import default_embeddings  # noqa # pylint: disable=unused-import
from .schema import UUID_COLUMN, PathTuple
from .signals.default_signals import register_default_signals
from .signals.signal import Signal
from .signals.signal_registry import resolve_signal
from .utils import DATASETS_DIR_NAME

router = APIRouter()

register_default_signals()


class DatasetInfo(BaseModel):
  """Information about a dataset."""
  namespace: str
  dataset_name: str
  description: Optional[str]


@router.get('/')
def get_datasets() -> list[DatasetInfo]:
  """List the datasets."""
  dataset_infos: list[DatasetInfo] = []
  datasets_path = os.path.join(data_path(), DATASETS_DIR_NAME)
  # Skip if 'datasets' doesn't exist.
  if not os.path.isdir(datasets_path):
    return []

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
  dataset_db = get_dataset_db(namespace, dataset_name)
  return WebManifest(dataset_manifest=dataset_db.manifest())


@router.post('/{namespace}/{dataset_name}/compute_embedding_index')
def compute_embedding_index(namespace: str, dataset_name: str, embedding: str, column: str) -> dict:
  """Compute a signal for a dataset."""
  dataset_db = get_dataset_db(namespace, dataset_name)
  dataset_db.compute_embedding_index(embedding, column)

  return {}


class ComputeSignalOptions(BaseModel):
  """The request for the compute signal endpoint."""
  signal: Signal

  # The columns to compute the signal on.
  column: str

  @validator('signal', pre=True)
  def parse_signal(cls, signal: dict) -> Signal:
    """Parse a signal to its specific subclass instance."""
    return resolve_signal(signal)


@router.post('/{namespace}/{dataset_name}/compute_signal_column')
def compute_signal_column(namespace: str, dataset_name: str, options: ComputeSignalOptions) -> dict:
  """Compute a signal for a dataset."""
  dataset_db = get_dataset_db(namespace, dataset_name)
  dataset_db.compute_signal_columns(options.signal, options.column)

  return {}


class GetStatsOptions(BaseModel):
  """The request for the get stats endpoint."""
  leaf_path: PathTuple


@router.post('/{namespace}/{dataset_name}/stats')
def get_stats(namespace: str, dataset_name: str, options: GetStatsOptions) -> StatsResult:
  """Get the stats for the dataset."""
  dataset_db = get_dataset_db(namespace, dataset_name)
  return dataset_db.stats(options.leaf_path)


class SelectRowsOptions(BaseModel):
  """The request for the select rows endpoint."""
  columns: Optional[list[str]]
  filters: Optional[list[Filter]]
  sort_by: Optional[list[str]]
  sort_order: Optional[SortOrder] = SortOrder.DESC
  limit: Optional[int]
  offset: Optional[int]


@router.post('/{namespace}/{dataset_name}/select_rows')
def select_rows(namespace: str, dataset_name: str, options: SelectRowsOptions) -> list[dict]:
  """Select rows from the dataset database."""
  db = get_dataset_db(namespace, dataset_name)

  columns: Optional[list[ColumnId]] = None
  if options.columns is not None:
    columns = [column for column in db.columns() if column.alias in options.columns]

  items = list(
      db.select_rows(columns=columns,
                     filters=options.filters,
                     sort_by=options.sort_by,
                     sort_order=options.sort_order,
                     limit=options.limit))

  for item in items:
    item[UUID_COLUMN] = item[UUID_COLUMN].hex()

  return items


class SelectGroupsOptions(BaseModel):
  """The request for the select groups endpoint."""
  leaf_path: PathTuple
  filters: Optional[list[Filter]]
  sort_by: Optional[GroupsSortBy] = GroupsSortBy.COUNT
  sort_order: Optional[SortOrder] = SortOrder.DESC
  limit: Optional[int]
  bins: Optional[Bins]


@router.post('/{namespace}/{dataset_name}/select_groups')
def select_groups(namespace: str, dataset_name: str, options: SelectGroupsOptions) -> list[dict]:
  """Select groups from the dataset database."""
  db = get_dataset_db(namespace, dataset_name)
  result = db.select_groups(options.leaf_path, options.filters, options.sort_by, options.sort_order,
                            options.limit, options.bins)
  return list(result)


@router.get('/{namespace}/{dataset_name}/media')
def get_media(namespace: str, dataset_name: str, item_id: str, leaf_path: str) -> Response:
  """Get the media for the dataset."""
  db = get_dataset_db(namespace, dataset_name)
  path = tuple(leaf_path.split('.'))
  result = db.media(item_id, path)
  # Return the response via HTTP.
  return Response(content=result.data)
