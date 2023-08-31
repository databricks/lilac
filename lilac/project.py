"""Project utilities."""
import os

from .config import Config
from .env import env
from .utils import to_yaml

PROJECT_CONFIG_FILENAME = 'lilac.yml'


def project_path_from_args(project_path_arg: str) -> str:
  """Returns the project path from the command line args."""
  project_path = project_path_arg
  if project_path_arg == '':
    project_path = env('LILAC_DATA_PATH', None)
  if not project_path:
    project_path = '.'

  return os.path.expanduser(project_path)


def dir_is_project(project_path: str) -> bool:
  """Returns whether the directory is a Lilac project."""
  if not os.path.isdir(project_path):
    return False

  return os.path.exists(os.path.join(project_path, PROJECT_CONFIG_FILENAME))


def create_project(project_path: str) -> None:
  """Creates an empty lilac project."""
  with open(os.path.join(project_path, PROJECT_CONFIG_FILENAME), 'w') as f:
    f.write('# Lilac project config. See https://lilacml.com/api_reference/index.html#lilac.Config '
            'for details.\n\n' +
            to_yaml(Config(datasets=[]).dict(exclude_defaults=True, exclude_none=True)))


def create_project_and_set_env(project_path_arg: str) -> None:
  """Creates a Lilac project if it doesn't exist and set the environment variable."""
  project_path = project_path_from_args(project_path_arg)
  if not dir_is_project(project_path):
    if not os.path.isdir(project_path):
      os.makedirs(project_path)

    create_project(project_path)

  os.environ['LILAC_DATA_PATH'] = project_path
