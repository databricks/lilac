"""Serves the Lilac server."""

import asyncio
import logging
import os
import webbrowser
from contextlib import asynccontextmanager
from importlib import metadata
from threading import Thread
from typing import Annotated, Any, AsyncGenerator, Optional

import uvicorn
from fastapi import APIRouter, BackgroundTasks, Depends, FastAPI, Request, Response
from fastapi.responses import (
  FileResponse,
  HTMLResponse,
  JSONResponse,
  ORJSONResponse,
  RedirectResponse,
)
from fastapi.routing import APIRoute
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from starlette.datastructures import URL
from starlette.middleware.sessions import SessionMiddleware
from starlette.types import ASGIApp, Receive, Scope, Send
from uvicorn.config import Config

from . import (
  router_concept,
  router_data_loader,
  router_dataset,
  router_dataset_signals,
  router_google_login,
  router_rag,
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
from .source import registered_sources

DIST_PATH = os.path.join(os.path.dirname(__file__), 'web')

tags_metadata: list[dict[str, Any]] = [
  {'name': 'datasets', 'description': 'API for querying a dataset.'},
  {'name': 'concepts', 'description': 'API for managing concepts.'},
  {'name': 'data_loaders', 'description': 'API for loading data.'},
  {'name': 'signals', 'description': 'API for managing signals.'},
]


def custom_generate_unique_id(route: APIRoute) -> str:
  """Generate the name for the API endpoint."""
  return route.name


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
  """Context manager for the lifespan of the application."""
  if env('LILAC_LOAD_ON_START_SERVER', False):

    def run() -> None:
      load(project_dir=get_project_dir(), overwrite=False)

    thread = Thread(target=run)
    thread.start()

  yield


app = FastAPI(
  default_response_class=ORJSONResponse,
  generate_unique_id_function=custom_generate_unique_id,
  openapi_tags=tags_metadata,
  lifespan=lifespan,
)


class HttpUrlRedirectMiddleware:
  """Middleware that redirects trailing slashes to non-trailing slashes."""

  def __init__(self, app: ASGIApp) -> None:
    self.app = app

  async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
    """Redirect trailing slashes to non-trailing slashes."""
    url = URL(scope=scope).path

    root_path = scope.get('root_path') or ''
    ends_with_slash = (
      url.endswith('/')
      and url != '/'
      and url != f'{root_path}/'
      and not url.startswith(root_path + '/api')
    )

    if scope['type'] == 'http' and ends_with_slash:
      new_url = url.rstrip('/')
      response = RedirectResponse(url=new_url, status_code=307)
      await response(scope, receive, send)
    else:
      await self.app(scope, receive, send)


@app.exception_handler(ConceptAuthorizationException)
def concept_authorization_exception(
  request: Request, exc: ConceptAuthorizationException
) -> JSONResponse:
  """Return a 401 JSON response when an authorization exception is thrown."""
  message = 'Oops! You are not authorized to do this.'
  return JSONResponse(status_code=401, content={'detail': message, 'message': message})


@app.exception_handler(ModuleNotFoundError)
def module_not_found_error(request: Request, exc: ModuleNotFoundError) -> JSONResponse:
  """Return a 500 JSON response when a module fails to import because of optional imports."""
  message = 'Oops! You are missing a python dependency. ' + str(exc)
  return JSONResponse(status_code=500, content={'detail': message, 'message': message})


app.add_middleware(SessionMiddleware, secret_key=env('LILAC_OAUTH_SECRET_KEY'))
app.add_middleware(HttpUrlRedirectMiddleware)
app.include_router(router_google_login.router, prefix='/google', tags=['google_login'])

v1_router = APIRouter(route_class=RouteErrorHandler)
v1_router.include_router(router_dataset.router, prefix='/datasets', tags=['datasets'])
v1_router.include_router(router_dataset_signals.router, prefix='/datasets', tags=['datasets'])
v1_router.include_router(router_concept.router, prefix='/concepts', tags=['concepts'])
v1_router.include_router(router_data_loader.router, prefix='/data_loaders', tags=['data_loaders'])
v1_router.include_router(router_signal.router, prefix='/signals', tags=['signals'])
v1_router.include_router(router_tasks.router, prefix='/tasks', tags=['tasks'])
v1_router.include_router(router_rag.router, prefix='/rag', tags=['rag'])

for source_name, source in registered_sources().items():
  if source.router:
    v1_router.include_router(source.router, prefix=f'/{source_name}', tags=[source_name])


@app.get('/auth_info')
def auth_info(user: Annotated[Optional[UserInfo], Depends(get_session_user)]) -> AuthenticationInfo:
  """Returns the user's ACL.

  NOTE: Validation happens server-side as well. This is just used for UI treatment.
  """
  auth_enabled = bool(env('LILAC_AUTH_ENABLED', False))
  return AuthenticationInfo(
    user=user,
    access=get_user_access(user),
    auth_enabled=auth_enabled,
    # See: https://huggingface.co/docs/hub/spaces-overview#helper-environment-variables
    huggingface_space_id=env('SPACE_ID', None),
  )


class ServerStatus(BaseModel):
  """Server status information."""

  version: str
  google_analytics_enabled: bool
  disable_error_notifications: bool


@app.get('/status')
def status() -> ServerStatus:
  """Returns server status information."""
  return ServerStatus(
    version=metadata.version('lilac'),
    google_analytics_enabled=env('GOOGLE_ANALYTICS_ENABLED', False),
    disable_error_notifications=env('LILAC_DISABLE_ERROR_NOTIFICATIONS', False),
  )


@app.post('/load_config')
def load_config(background_tasks: BackgroundTasks) -> dict:
  """Loads from the lilac.yml."""
  background_tasks.add_task(load, project_dir=get_project_dir(), overwrite=False)
  return {}


app.include_router(v1_router, prefix='/api/v1')

current_dir = os.path.dirname(os.path.abspath(__file__))
templates = Jinja2Templates(directory=os.path.join(current_dir, 'templates'))


@app.get('/_data{path:path}', response_class=HTMLResponse, include_in_schema=False)
def list_files(
  request: Request, path: str, user: Annotated[Optional[UserInfo], Depends(get_session_user)]
) -> Response:
  """List files in the data directory."""
  if env('LILAC_AUTH_ENABLED', False) and not get_user_access(user).is_admin:
    return Response(status_code=401)
  path = os.path.join(get_project_dir(), f'.{path}')
  if not os.path.exists(path):
    return Response(status_code=404)
  if os.path.isfile(path):
    return FileResponse(path)

  files = os.listdir(path)
  files_paths = sorted([(os.path.join(request.url.path, f), f) for f in files])
  return templates.TemplateResponse('list_files.html', {'request': request, 'files': files_paths})


# Serve static files in production mode.
app.mount(
  '/_app', StaticFiles(directory=os.path.join(DIST_PATH, '_app'), html=True, check_dir=False)
)


@app.get('/favicon.ico', include_in_schema=False)
async def favicon() -> FileResponse:
  """Serve the favicon which must be in the root of the dist folder."""
  return FileResponse(os.path.join(DIST_PATH, 'favicon.ico'))


@app.api_route('/{path_name:path}', include_in_schema=False)
def catch_all(path_name: str) -> FileResponse:
  """Catch any other requests and serve index for HTML5 history."""
  filename = f'{path_name or "index"}.html'
  return FileResponse(path=os.path.join(DIST_PATH, filename))


class GetTasksFilter(logging.Filter):
  """Task filter for /tasks."""

  def filter(self, record: logging.LogRecord) -> bool:
    """Filters out /api/v1/tasks/ from the logs."""
    return record.getMessage().find('/api/v1/tasks/') == -1


logging.getLogger('uvicorn.access').addFilter(GetTasksFilter())


class Server(uvicorn.Server):
  """Server that runs in a separate thread."""

  def __init__(self, config: Config) -> None:
    super().__init__(config)

  def start(self, block: bool = True) -> None:
    """Start the server in a separate thread."""

    def run() -> None:
      try:
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.serve())
      except RuntimeError:
        self.run()

    if block:
      run()
    else:
      self.thread = Thread(target=run, daemon=True)
      self.thread.start()

  def stop(self) -> None:
    """Stop the server."""
    self.should_exit = True
    self.thread.join()


SERVER: Optional[Server] = None


def start_server(
  host: str = '127.0.0.1',
  port: int = 5432,
  open: bool = False,
  project_dir: str = '',
  load: bool = False,
) -> Server:
  """Starts the Lilac web server.

  Args:
    host: The host to run the server on.
    port: The port to run the server on.
    open: Whether to open a browser tab upon startup.
    project_dir: The path to the Lilac project directory. If not specified, the `LILAC_PROJECT_DIR`
      environment variable will be used (this can be set from `set_project_dir`). If
      `LILAC_PROJECT_DIR` is not defined, will start in the current directory.
    load: Whether to load from the lilac.yml when the server boots up. This will diff the config
      with the fields that are computed and compute them when the server boots up.
  """
  create_project_and_set_env(project_dir)

  global SERVER
  if SERVER:
    raise ValueError('Server is already running')

  if load:
    os.environ['LILAC_LOAD_ON_START_SERVER'] = 'true'

  if open:

    @app.on_event('startup')
    def open_browser() -> None:
      webbrowser.open(f'http://{host}:{port}')

  block = False
  try:
    asyncio.get_running_loop()
  except RuntimeError:
    block = True

  config = uvicorn.Config(app, host=host, port=port, access_log=False)
  SERVER = Server(config)
  SERVER.start(block=block)

  return SERVER


def stop_server() -> None:
  """Stops the Lilac web server."""
  global SERVER
  if SERVER is None:
    return
  SERVER.stop()
  SERVER = None
