"""Serves the Lilac server."""

import asyncio
import logging
import os
import time
import webbrowser
from importlib import metadata
from typing import Any, Optional

import requests
import uvicorn
from fastapi import APIRouter, BackgroundTasks, FastAPI, Request, Response
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, ORJSONResponse
from fastapi.routing import APIRoute
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from starlette.middleware.sessions import SessionMiddleware

from . import (
  router_concept,
  router_data_loader,
  router_dataset,
  router_google_login,
  router_signal,
  router_tasks,
)
from .auth import (
  AuthenticationInfo,
  ConceptAuthorizationException,
  UserInfo,
  get_session_user,
  get_user_access,
)
from .env import env, get_project_dir
from .load import load
from .project import create_project_and_set_env
from .router_utils import RouteErrorHandler
from .sources.default_sources import register_default_sources
from .sources.source_registry import registered_sources
from .tasks import get_task_manager

register_default_sources()

DIST_PATH = os.path.join(os.path.dirname(__file__), 'web')

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


@app.exception_handler(ConceptAuthorizationException)
def concept_authorization_exception(request: Request,
                                    exc: ConceptAuthorizationException) -> JSONResponse:
  """Return a 401 JSON response when an authorization exception is thrown."""
  message = 'Oops! You are not authorized to do this.'
  return JSONResponse(
    status_code=401,
    content={
      'detail': message,
      'message': message
    },
  )


@app.exception_handler(ModuleNotFoundError)
def module_not_found_error(request: Request, exc: ModuleNotFoundError) -> JSONResponse:
  """Return a 500 JSON response when a module fails to import because of optional imports."""
  message = 'Oops! You are missing a python dependency. ' + str(exc)
  return JSONResponse(
    status_code=500,
    content={
      'detail': message,
      'message': message
    },
  )


app.add_middleware(SessionMiddleware, secret_key=env('LILAC_OAUTH_SECRET_KEY'))

app.include_router(router_google_login.router, prefix='/google', tags=['google_login'])

v1_router = APIRouter(route_class=RouteErrorHandler)
v1_router.include_router(router_dataset.router, prefix='/datasets', tags=['datasets'])
v1_router.include_router(router_concept.router, prefix='/concepts', tags=['concepts'])
v1_router.include_router(router_data_loader.router, prefix='/data_loaders', tags=['data_loaders'])
v1_router.include_router(router_signal.router, prefix='/signals', tags=['signals'])
v1_router.include_router(router_tasks.router, prefix='/tasks', tags=['tasks'])

for source_name, source in registered_sources().items():
  if source.router:
    v1_router.include_router(source.router, prefix=f'/{source_name}', tags=[source_name])


@app.get('/auth_info')
def auth_info(request: Request) -> AuthenticationInfo:
  """Returns the user's ACL.

  NOTE: Validation happens server-side as well. This is just used for UI treatment.
  """
  user_info: Optional[UserInfo] = get_session_user(request)
  return AuthenticationInfo(
    user=user_info,
    access=get_user_access(),
    auth_enabled=env('LILAC_AUTH_ENABLED', False),
    # See: https://huggingface.co/docs/hub/spaces-overview#helper-environment-variables
    huggingface_space_id=env('SPACE_ID', None))


class ServerStatus(BaseModel):
  """Server status information."""
  version: str
  google_analytics_enabled: bool


@app.get('/status')
def status() -> ServerStatus:
  """Returns server status information."""
  return ServerStatus(
    version=metadata.version('lilac'),
    google_analytics_enabled=env('GOOGLE_ANALYTICS_ENABLED', False))


@app.post('/load_config')
def load_config(background_tasks: BackgroundTasks) -> dict:
  """Loads from the lilac.yml."""

  async def _load() -> None:
    load(project_dir=get_project_dir(), overwrite=False, task_manager=get_task_manager())

  background_tasks.add_task(_load)
  return {}


app.include_router(v1_router, prefix='/api/v1')

current_dir = os.path.dirname(os.path.abspath(__file__))
templates = Jinja2Templates(directory=os.path.join(current_dir, 'templates'))


@app.get('/_data{path:path}', response_class=HTMLResponse, include_in_schema=False)
def list_files(request: Request, path: str) -> Response:
  """List files in the data directory."""
  if env('LILAC_AUTH_ENABLED', False):
    return Response(status_code=401)
  path = os.path.join(get_project_dir(), f'.{path}')
  if not os.path.exists(path):
    return Response(status_code=404)
  if os.path.isfile(path):
    return FileResponse(path)

  files = os.listdir(path)
  files_paths = sorted([(os.path.join(request.url.path, f), f) for f in files])
  return templates.TemplateResponse('list_files.html', {'request': request, 'files': files_paths})


@app.api_route('/{path_name}', include_in_schema=False)
def catch_all() -> FileResponse:
  """Catch any other requests and serve index for HTML5 history."""
  return FileResponse(path=os.path.join(DIST_PATH, 'index.html'))


# Serve static files in production mode.
app.mount('/', StaticFiles(directory=DIST_PATH, html=True, check_dir=False))


@app.on_event('shutdown')
async def shutdown_event() -> None:
  """Kill the task manager when FastAPI shuts down."""
  await get_task_manager().stop()


class GetTasksFilter(logging.Filter):
  """Task filter for /tasks."""

  def filter(self, record: logging.LogRecord) -> bool:
    """Filters out /api/v1/tasks/ from the logs."""
    return record.getMessage().find('/api/v1/tasks/') == -1


logging.getLogger('uvicorn.access').addFilter(GetTasksFilter())

SERVER: Optional[uvicorn.Server] = None


def start_server(host: str = '127.0.0.1',
                 port: int = 5432,
                 open: bool = False,
                 project_dir: str = '',
                 skip_load: bool = False) -> None:
  """Starts the Lilac web server.

  Args:
    host: The host to run the server on.
    port: The port to run the server on.
    open: Whether to open a browser tab upon startup.
    project_dir: The path to the Lilac project directory. If not specified, the `LILAC_PROJECT_DIR`
      environment variable will be used (this can be set from `set_project_dir`). If
      `LILAC_PROJECT_DIR` is not defined, will start in the current directory.
    skip_load: Whether to skip loading from the lilac.yml when the server boots up.
  """
  create_project_and_set_env(project_dir)

  global SERVER
  if SERVER:
    raise ValueError('Server is already running')

  config = uvicorn.Config(
    app,
    host=host,
    port=port,
    access_log=False,
  )
  SERVER = uvicorn.Server(config)

  if open:

    @app.on_event('startup')
    def open_browser() -> None:
      webbrowser.open(f'http://{host}:{port}')

      if not skip_load:

        def _post_load() -> None:
          server_ready = False
          while not server_ready:
            try:
              server_ready = requests.get((f'http://{host}:{port}/status'),
                                          timeout=.200).status_code == 200
            except Exception as e:
              server_ready = False
            time.sleep(.1)
          try:
            # Load the config.
            requests.post(f'http://{host}:{port}/load_config')
          except Exception as e:
            print('Error loading config: ', e)

        loop = asyncio.get_running_loop()
        loop.run_in_executor(None, _post_load)

  try:
    loop = asyncio.get_event_loop()
    if loop.is_running():
      loop.create_task(SERVER.serve())
    else:
      SERVER.run()
  except RuntimeError:
    SERVER.run()


async def stop_server() -> None:
  """Stops the Lilac web server."""
  global SERVER
  if SERVER is None:
    raise ValueError('Server is not running')
  await SERVER.shutdown()
  SERVER = None
