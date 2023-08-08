"""The source loader runner which loads data into parquet files for the app.

To run the source loader as a binary directly:

poetry run python -m lilac.datasets.loader \
  --dataset_name=$DATASET \
  --output_dir=./data/ \
  --config_path=./datasets/the_movies_dataset.json
"""
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from .auth import get_user_access
from .config import DatasetConfig
from .data_loader import process_source
from .env import data_path
from .router_utils import RouteErrorHandler
from .sources.source_registry import get_source_cls, registered_sources
from .tasks import TaskId, task_manager

REQUEST_TIMEOUT_SEC = 30 * 60  # 30 mins.

router = APIRouter(route_class=RouteErrorHandler)


class ProcessSourceRequest(BaseModel):
  """The interface to the /process_source endpoint."""
  username: str
  dataset_name: str


class SourcesList(BaseModel):
  """The interface to the /process_source endpoint."""
  sources: list[str]


@router.get('/')
def get_sources() -> SourcesList:
  """Get the list of available sources."""
  sources = registered_sources()
  return SourcesList(sources=list(sources.keys()))


@router.get('/{source_name}')
def get_source_schema(source_name: str) -> dict[str, Any]:
  """Get the fields for a source."""
  source_cls = get_source_cls(source_name)
  if source_cls is None:
    raise ValueError(f'Unknown source: {source_name}')
  return source_cls.schema()


class LoadDatasetOptions(BaseModel):
  """Options for loading a dataset."""
  namespace: str
  dataset_name: str
  config: dict[str, Any]


class LoadDatasetResponse(BaseModel):
  """Response of the load dataset endpoint."""
  task_id: TaskId


@router.post('/{source_name}/load')
async def load(source_name: str, options: LoadDatasetOptions,
               request: Request) -> LoadDatasetResponse:
  """Load a dataset."""
  if not get_user_access().create_dataset:
    raise HTTPException(401, 'User does not have access to load a dataset.')

  source_cls = get_source_cls(source_name)
  if source_cls is None:
    raise ValueError(f'Unknown source: {source_name}')
  source = source_cls(**options.config)

  task_id = task_manager().task_id(
    name=f'[{options.namespace}/{options.dataset_name}] Load dataset',
    description=f'Loader: {source.name}. \n Config: {source}')
  task_manager().execute(
    task_id, process_source, data_path(),
    DatasetConfig(namespace=options.namespace, name=options.dataset_name, source=source),
    (task_id, 0))

  return LoadDatasetResponse(task_id=task_id)
