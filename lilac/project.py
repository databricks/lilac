"""Project utilities."""
import os
import pathlib
import threading
from typing import Optional, Union

import yaml

from .config import (
  Config,
  DatasetConfig,
  DatasetSettings,
  EmbeddingConfig,
  SignalConfig,
  get_dataset_config,
)
from .env import env, get_project_dir, set_project_dir
from .utils import log, to_yaml

PROJECT_CONFIG_FILENAME = 'lilac.yml'
PROJECT_CONFIG_LOCK = threading.Lock()


def init(project_dir: Optional[Union[str, pathlib.Path]] = None) -> None:
  """Initializes a project."""
  project_dir = project_dir or get_project_dir()
  if dir_is_project(project_dir):
    raise ValueError(f'{project_dir} is already a project.')

  create_project(project_dir)

  log(f'Successfully initialized project at {project_dir}')


def add_project_dataset_config(
  dataset_config: DatasetConfig,
  project_dir: Optional[Union[str, pathlib.Path]] = None,
  overwrite: bool = False,
) -> None:
  """Add a dataset to the project config.

  Args:
    dataset_config: The dataset configuration to load.
    project_dir: The path to the project directory for where to create the dataset. If not defined,
      uses the project directory from `LILAC_PROJECT_DIR` or [deprecated] `LILAC_DATA_PATH`.
    overwrite: Whether to overwrite the dataset if it already exists.
  """
  project_dir = project_dir or get_project_dir()
  with PROJECT_CONFIG_LOCK:
    config = read_project_config(project_dir)
    existing_dataset_config = get_dataset_config(
      config, dataset_config.namespace, dataset_config.name
    )
    if existing_dataset_config is not None:
      if overwrite:
        config.datasets.remove(existing_dataset_config)
      else:
        raise ValueError(
          f'{dataset_config} has already been added. You can delete it with: \n\n'
          f'dataset = get_dataset("{dataset_config.namespace}", "{dataset_config.name}")\n'
          'dataset.delete()'
        )

    config.datasets.append(dataset_config)
    write_project_config(project_dir, config)


def delete_project_dataset_config(
  namespace: str, dataset_name: str, project_dir: Optional[Union[str, pathlib.Path]] = None
) -> None:
  """Delete a dataset config in a project."""
  project_dir = project_dir or get_project_dir()

  with PROJECT_CONFIG_LOCK:
    config = read_project_config(project_dir)
    dataset_config = get_dataset_config(config, namespace, dataset_name)
    if dataset_config is None:
      raise ValueError(f'{dataset_config} not found in project config.')

    config.datasets.remove(dataset_config)
    write_project_config(project_dir, config)


def update_project_dataset_settings(
  dataset_namespace: str,
  dataset_name: str,
  settings: DatasetSettings,
  project_dir: Optional[Union[str, pathlib.Path]] = None,
) -> None:
  """Update the settings of a dataset config in a project."""
  project_dir = project_dir or get_project_dir()

  with PROJECT_CONFIG_LOCK:
    config = read_project_config(project_dir)
    dataset_config = get_dataset_config(config, dataset_namespace, dataset_name)
    if dataset_config is None:
      raise ValueError(f'Dataset "{dataset_namespace}/{dataset_name}" not found in project config.')
    dataset_config.settings = settings
    write_project_config(project_dir, config)


def add_project_signal_config(
  dataset_namespace: str,
  dataset_name: str,
  signal_config: SignalConfig,
  project_dir: Optional[Union[str, pathlib.Path]] = None,
) -> None:
  """Add a dataset signal to the project config."""
  project_dir = project_dir or get_project_dir()

  with PROJECT_CONFIG_LOCK:
    config = read_project_config(project_dir)
    dataset_config = get_dataset_config(config, dataset_namespace, dataset_name)
    if dataset_config is None:
      raise ValueError(
        f'Dataset "{dataset_namespace}/{dataset_name}" not found in project config in '
        f'project dir: {project_dir}.'
      )
    if signal_config in dataset_config.signals:
      return
    dataset_config.signals.append(signal_config)
    write_project_config(project_dir, config)


def add_project_embedding_config(
  dataset_namespace: str,
  dataset_name: str,
  embedding_config: EmbeddingConfig,
  project_dir: Optional[Union[str, pathlib.Path]] = None,
) -> None:
  """Add a dataset embedding to the project config."""
  project_dir = project_dir or get_project_dir()

  with PROJECT_CONFIG_LOCK:
    config = read_project_config(project_dir)
    dataset_config = get_dataset_config(config, dataset_namespace, dataset_name)
    if dataset_config is None:
      raise ValueError(f'Dataset "{dataset_namespace}/{dataset_name}" not found in project config.')

    if embedding_config in dataset_config.embeddings:
      return

    dataset_config.embeddings.append(embedding_config)
    write_project_config(project_dir, config)


def delete_project_signal_config(
  dataset_namespace: str,
  dataset_name: str,
  signal_config: SignalConfig,
  project_dir: Optional[Union[str, pathlib.Path]] = None,
) -> None:
  """Delete a dataset signal from the project config."""
  project_dir = project_dir or get_project_dir()

  with PROJECT_CONFIG_LOCK:
    config = read_project_config(project_dir)
    dataset_config = get_dataset_config(config, dataset_namespace, dataset_name)
    if dataset_config is None:
      raise ValueError(f'{dataset_config} not found in project config.')
    dataset_config.signals = [
      s for s in dataset_config.signals if s.model_dump() != signal_config.model_dump()
    ]
    write_project_config(project_dir, config)


def project_dir_from_args(project_dir_arg: str) -> str:
  """Returns the project directory from the command line args."""
  project_dir = project_dir_arg
  if project_dir_arg == '':
    project_dir = env('LILAC_PROJECT_DIR', None) or env('LILAC_DATA_PATH', None)
  if not project_dir:
    project_dir = '.'

  return os.path.expanduser(project_dir)


def dir_is_project(project_dir: Union[str, pathlib.Path]) -> bool:
  """Returns whether the directory is a Lilac project."""
  if not os.path.isdir(project_dir):
    return False

  return os.path.exists(os.path.join(project_dir, PROJECT_CONFIG_FILENAME))


def read_project_config(project_dir: Union[str, pathlib.Path]) -> Config:
  """Reads the project config."""
  project_config_filepath = os.path.join(project_dir, PROJECT_CONFIG_FILENAME)
  if not os.path.exists(project_config_filepath):
    create_project(project_dir)

  with open(project_config_filepath) as f:
    config_dict = yaml.safe_load(f.read()) or {}
    return Config(**config_dict)


def write_project_config(project_dir: Union[str, pathlib.Path], config: Config) -> None:
  """Writes the project config."""
  with open(os.path.join(project_dir, PROJECT_CONFIG_FILENAME), 'w') as f:
    yaml_config = to_yaml(config.model_dump(exclude_defaults=True, exclude_none=True))
    f.write(
      '# Lilac project config.\n'
      + '# See https://lilacml.com/api_reference/index.html#lilac.Config '
      'for details.\n\n' + yaml_config
    )


def create_project(project_dir: Union[str, pathlib.Path]) -> None:
  """Creates an empty lilac project if it's not already a project."""
  if not dir_is_project(project_dir):
    os.makedirs(project_dir, exist_ok=True)

    write_project_config(project_dir, Config(datasets=[]))


def create_project_and_set_env(project_dir_arg: str) -> None:
  """Creates a Lilac project if it doesn't exist and set the environment variable."""
  project_dir = project_dir_from_args(project_dir_arg)
  create_project(project_dir)
  set_project_dir(project_dir)
