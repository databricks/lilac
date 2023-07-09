"""Serves the Lilac server."""

import logging
import os
import shutil
import subprocess
from typing import Any

from fastapi import APIRouter, FastAPI
from fastapi.responses import FileResponse, ORJSONResponse
from fastapi.routing import APIRoute
from fastapi.staticfiles import StaticFiles
from huggingface_hub import snapshot_download

from . import router_concept, router_data_loader, router_dataset, router_signal, router_tasks
from .config import CONFIG, data_path
from .router_utils import RouteErrorHandler
from .tasks import task_manager
from .utils import get_dataset_output_dir, list_datasets

DIST_PATH = os.path.abspath(os.path.join('web', 'blueprint', 'build'))

tags_metadata: list[dict[str, Any]] = [{
  'name': 'datasets',
  'description': 'API for querying a dataset.',
}, {
  'name': 'concepts',
  'description': 'API for managing concepts.',
}, {
  'name': 'data_loaders',
  'description': 'API for loading data.',
}, {
  'name': 'signals',
  'description': 'API for managing signals.',
}]


def custom_generate_unique_id(route: APIRoute) -> str:
  """Generate the name for the API endpoint."""
  return route.name


app = FastAPI(
  default_response_class=ORJSONResponse,
  generate_unique_id_function=custom_generate_unique_id,
  openapi_tags=tags_metadata)

v1_router = APIRouter(route_class=RouteErrorHandler)
v1_router.include_router(router_dataset.router, prefix='/datasets', tags=['datasets'])
v1_router.include_router(router_concept.router, prefix='/concepts', tags=['concepts'])
v1_router.include_router(router_data_loader.router, prefix='/data_loaders', tags=['data_loaders'])
v1_router.include_router(router_signal.router, prefix='/signals', tags=['signals'])
v1_router.include_router(router_tasks.router, prefix='/tasks', tags=['tasks'])

app.include_router(v1_router, prefix='/api/v1')


@app.api_route('/{path_name}', include_in_schema=False)
def catch_all() -> FileResponse:
  """Catch any other requests and serve index for HTML5 history."""
  return FileResponse(path=os.path.join(DIST_PATH, 'index.html'))


# Serve static files in production mode.
app.mount('/', StaticFiles(directory=DIST_PATH, html=True, check_dir=False))


@app.on_event('startup')
def startup() -> None:
  """Download dataset files from the HF space that was uploaded before building the image."""
  repo_id = CONFIG.get('HF_DATA_FROM_SPACE', None)

  if repo_id:
    # Download the huggingface space data. This includes code and datasets, so we move the datasets
    # alone to the data directory.
    spaces_download_dir = os.path.join(data_path(), '.hf_spaces', repo_id)
    snapshot_download(
      repo_id=repo_id,
      repo_type='space',
      local_dir=spaces_download_dir,
      local_dir_use_symlinks=False,
      token=CONFIG['HF_ACCESS_TOKEN'])

    datasets = list_datasets(os.path.join(spaces_download_dir, 'data'))
    for dataset in datasets:
      spaces_dataset_output_dir = get_dataset_output_dir(
        os.path.join(spaces_download_dir, 'data'), dataset.namespace, dataset.dataset_name)
      persistent_output_dir = get_dataset_output_dir(data_path(), dataset.namespace,
                                                     dataset.dataset_name)

      # Huggingface doesn't let you selectively download files so we just copy the data directory
      # out of the cloned space.
      shutil.rmtree(persistent_output_dir, ignore_errors=True)
      shutil.move(spaces_dataset_output_dir, persistent_output_dir)


def run(cmd: str) -> subprocess.CompletedProcess[bytes]:
  """Run a command and return the result."""
  return subprocess.run(cmd, shell=True, check=True)


@app.on_event('shutdown')
async def shutdown_event() -> None:
  """Kill the task manager when FastAPI shuts down."""
  await task_manager().stop()


class GetTasksFilter(logging.Filter):
  """Task filter for /tasks."""

  def filter(self, record: logging.LogRecord) -> bool:
    """Filters out /api/v1/tasks/ from the logs."""
    return record.getMessage().find('/api/v1/tasks/') == -1


logging.getLogger('uvicorn.access').addFilter(GetTasksFilter())
