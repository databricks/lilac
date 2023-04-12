"""The source loader runner which loads data into parquet files for the app.

To run the source loader as a binary directly:

poetry run python -m src.datasets.loader \
  --dataset_name=$DATASET \
  --output_dir=./gcs_cache/ \
  --config_path=./datasets/the_movies_dataset.json
"""
from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel

from .constants import data_path
from .data.sources.default_sources import register_default_sources
from .data.sources.source_registry import get_source_cls, registered_sources
from .data_loader import process_source
from .router_utils import RouteErrorHandler
from .tasks import TaskId, task_manager

REQUEST_TIMEOUT_SEC = 30 * 60  # 30 mins.

register_default_sources()

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
  source_cls = get_source_cls(source_name)
  source = source_cls(**options.config)

  task_id = task_manager().task_id(
      name=f'Loading dataset {options.namespace}/{options.dataset_name}',
      description=f'Loader: {source.name}. \n Config: {source}')
  task_manager().execute(task_id, process_source, data_path(), options.namespace,
                         options.dataset_name, source, task_id)

  return LoadDatasetResponse(task_id=task_id)
