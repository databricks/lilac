"""Router for the dataset database."""
import os
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from .constants import data_path
from .datasets.db_dataset import ColumnId
from .db_manager import get_dataset_db
from .embeddings import default_embeddings  # noqa # pylint: disable=unused-import
from .schema import UUID_COLUMN
from .server_api import (
    ComputeEmbeddingIndexOptions,
    ComputeSignalOptions,
    SelectDatasetRowsOptions,
    WebColumnInfo,
    WebManifest,
)
from .signals.default_signals import register_default_signals

router = APIRouter()

register_default_signals()


class DatasetInfo(BaseModel):
  """Information about a dataset."""
  namespace: str
  dataset_name: str
  description: Optional[str]


@router.get('/datasets')
def get_datasets() -> list[DatasetInfo]:
  """List the datasets."""
  dataset_infos: list[DatasetInfo] = []
  for root, _, files in os.walk(os.path.join(data_path(), 'datasets')):
    print(root)
    if len(files) > 0:
      subdir = root[len(data_path() + '/'):]
      split = list(filter(lambda path: path != '', os.path.split(subdir)))
      if len(split) == 2:  # The subdir is a (namespace, dataset_name)
        namespace, dataset_name = split
        dataset_infos.append(DatasetInfo(namespace=namespace, dataset_name=dataset_name))

  print(dataset_infos)
  return dataset_infos


@router.get('/{namespace}/{dataset_name}/manifest')
def manifest(namespace: str, dataset_name: str) -> dict:
  """Get the web manifest for the dataset."""
  dataset_db = get_dataset_db(namespace, dataset_name)
  web_manifest = WebManifest(
      columns=[WebColumnInfo(name=column.alias) for column in dataset_db.columns()])
  return web_manifest.dict()


@router.post('/{namespace}/{dataset_name}/compute_embedding_index')
def compute_embedding_index(namespace: str, dataset_name: str,
                            options: ComputeEmbeddingIndexOptions) -> dict:
  """Compute a signal for a dataset."""
  dataset_db = get_dataset_db(namespace, dataset_name)

  dataset_db.compute_embedding_index(options.embedding, options.column)

  return {}


@router.post('/{namespace}/{dataset_name}/compute_signal_column')
def compute_signal_column(namespace: str, dataset_name: str, options: ComputeSignalOptions) -> dict:
  """Compute a signal for a dataset."""
  dataset_db = get_dataset_db(namespace, dataset_name)
  dataset_db.compute_signal_columns(options.signal, options.column)

  return {}


@router.get('/{namespace}/{dataset_name}/select_rows')
def select_rows(namespace: str, dataset_name: str,
                options: SelectDatasetRowsOptions = Depends()) -> list:
  """Select rows from the dataset database."""
  dataset_db = get_dataset_db(namespace, dataset_name)

  # Split the columns by ',' to generate the columns. FastAPI does not support parsing pydantic
  # lists directly.
  # See: https://stackoverflow.com/questions/63881885/fastapi-get-request-with-pydantic-list-field
  columns: Optional[list[ColumnId]] = None
  if options.columns is not None:
    query_columns = options.columns.split(',')
    columns = [column for column in dataset_db.columns() if column.alias in query_columns]

  sort_by = None
  if options.sort_by is not None:
    sort_by = options.sort_by.split(',')

  items = list(
      dataset_db.select_rows(
          columns=columns,
          # TODO(nsthorat): Support filters in the GET request.
          filters=[],
          sort_by=sort_by,
          sort_order=options.sort_order,
          limit=options.limit))

  for item in items:
    item[UUID_COLUMN] = item[UUID_COLUMN].hex()

  return list(items)
