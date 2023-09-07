"""Project utilities."""
import os
import threading

import yaml

from .config import (
  Config,
  DatasetConfig,
  DatasetSettings,
  EmbeddingConfig,
  SignalConfig,
  get_dataset_config,
)
from .env import data_path, env
from .utils import to_yaml

PROJECT_CONFIG_FILENAME = 'lilac.yml'
PROJECT_CONFIG_LOCK = threading.Lock()


def add_project_dataset_config(dataset_config: DatasetConfig) -> None:
  """Add a dataset to the project config."""
  with PROJECT_CONFIG_LOCK:
    config = read_project_config(data_path())
    existing_dataset_config = get_dataset_config(config, dataset_config.namespace,
                                                 dataset_config.name)
    if existing_dataset_config is not None:
      raise ValueError(f'{dataset_config} has already been added.')

    config.datasets.append(dataset_config)
    _write_project_config(data_path(), config)


def delete_project_dataset_config(namespace: str, dataset_name: str) -> None:
  """Delete a dataset config in a project."""
  with PROJECT_CONFIG_LOCK:
    config = read_project_config(data_path())
    dataset_config = get_dataset_config(config, namespace, dataset_name)
    if dataset_config is None:
      raise ValueError(f'{dataset_config} not found in project config.')

    config.datasets.remove(dataset_config)
    _write_project_config(data_path(), config)


def update_project_dataset_settings(dataset_namespace: str, dataset_name: str,
                                    settings: DatasetSettings) -> None:
  """Update the settings of a dataset config in a project."""
  with PROJECT_CONFIG_LOCK:
    config = read_project_config(data_path())
    dataset_config = get_dataset_config(config, dataset_namespace, dataset_name)
    if dataset_config is None:
      raise ValueError('Dataset not found in project config.')
    dataset_config.settings = settings
    _write_project_config(data_path(), config)


def add_project_signal_config(dataset_namespace: str, dataset_name: str,
                              signal_config: SignalConfig) -> None:
  """Add a dataset signal to the project config."""
  with PROJECT_CONFIG_LOCK:
    config = read_project_config(data_path())
    dataset_config = get_dataset_config(config, dataset_namespace, dataset_name)
    if dataset_config is None:
      raise ValueError('Dataset not found in project config.')
    if signal_config in dataset_config.signals:
      return
    dataset_config.signals.append(signal_config)
    _write_project_config(data_path(), config)


def add_project_embedding_config(dataset_namespace: str, dataset_name: str,
                                 embedding_config: EmbeddingConfig) -> None:
  """Add a dataset embedding to the project config."""
  with PROJECT_CONFIG_LOCK:
    config = read_project_config(data_path())
    dataset_config = get_dataset_config(config, dataset_namespace, dataset_name)
    if dataset_config is None:
      raise ValueError('Dataset not found in project config.')

    if embedding_config in dataset_config.embeddings:
      return

    dataset_config.embeddings.append(embedding_config)
    _write_project_config(data_path(), config)


def delete_project_signal_config(dataset_namespace: str, dataset_name: str,
                                 signal_config: SignalConfig) -> None:
  """Delete a dataset signal from the project config."""
  with PROJECT_CONFIG_LOCK:
    config = read_project_config(data_path())
    dataset_config = get_dataset_config(config, dataset_namespace, dataset_name)
    if dataset_config is None:
      raise ValueError(f'{dataset_config} not found in project config.')
    if signal_config not in dataset_config.signals:
      raise ValueError(f'{signal_config} not found in project config.')

    dataset_config.signals.remove(signal_config)
    _write_project_config(data_path(), config)


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


def read_project_config(project_path: str) -> Config:
  """Reads the project config."""
  project_config_filepath = os.path.join(project_path, PROJECT_CONFIG_FILENAME)
  if not os.path.exists(project_config_filepath):
    create_project(project_path)

  with open(os.path.join(project_path, PROJECT_CONFIG_FILENAME), 'r') as f:
    return Config(**yaml.safe_load(f.read()))


def _write_project_config(project_path: str, config: Config) -> None:
  """Writes the project config."""
  with open(os.path.join(project_path, PROJECT_CONFIG_FILENAME), 'w') as f:
    yaml_config = to_yaml(config.dict(exclude_defaults=True, exclude_none=True))
    f.write('# Lilac project config.\n' +
            '# See https://lilacml.com/api_reference/index.html#lilac.Config '
            'for details.\n\n' + yaml_config)


def create_project(project_path: str) -> None:
  """Creates an empty lilac project if it's not already a project."""
  if not dir_is_project(project_path):
    if not os.path.isdir(project_path):
      os.makedirs(project_path)

    _write_project_config(project_path, Config(datasets=[]))


def create_project_and_set_env(project_path_arg: str) -> None:
  """Creates a Lilac project if it doesn't exist and set the environment variable."""
  project_path = project_path_from_args(project_path_arg)
  create_project(project_path)

  os.environ['LILAC_DATA_PATH'] = project_path
