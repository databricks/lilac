"""Manages mapping the dataset name to the database instance."""
import os
import pathlib
import threading
from typing import Optional, Type, Union

from pydantic import BaseModel

from .config import get_dataset_config
from .data.dataset import Dataset
from .env import get_project_dir
from .project import read_project_config
from .utils import get_datasets_dir

_DEFAULT_DATASET_CLS: Type[Dataset]

_CACHED_DATASETS: dict[str, Dataset] = {}

_db_lock = threading.Lock()


def _dataset_cache_key(
  namespace: str, dataset_name: str, project_dir: Union[str, pathlib.Path]
) -> str:
  """Get the cache key for a dataset."""
  return f'{os.path.abspath(project_dir)}/{namespace}/{dataset_name}'


def get_dataset(
  namespace: str, dataset_name: str, project_dir: Optional[Union[str, pathlib.Path]] = None
) -> Dataset:
  """Get the dataset instance."""
  if not _DEFAULT_DATASET_CLS:
    raise ValueError('Default dataset class not set.')

  project_dir = project_dir or get_project_dir()

  cache_key = _dataset_cache_key(namespace, dataset_name, project_dir)
  # https://docs.pytest.org/en/latest/example/simple.html#pytest-current-test-environment-variable
  inside_test = 'PYTEST_CURRENT_TEST' in os.environ
  with _db_lock:
    if cache_key not in _CACHED_DATASETS or inside_test:
      _CACHED_DATASETS[cache_key] = _DEFAULT_DATASET_CLS(
        namespace=namespace, dataset_name=dataset_name, project_dir=project_dir
      )
    return _CACHED_DATASETS[cache_key]


def remove_dataset_from_cache(
  namespace: str, dataset_name: str, project_dir: Optional[Union[str, pathlib.Path]] = None
) -> None:
  """Remove the dataset from the db manager cache."""
  project_dir = project_dir or get_project_dir()

  cache_key = _dataset_cache_key(namespace, dataset_name, project_dir)
  with _db_lock:
    if cache_key in _CACHED_DATASETS:
      del _CACHED_DATASETS[cache_key]


class DatasetInfo(BaseModel):
  """Information about a dataset."""

  namespace: str
  dataset_name: str
  description: Optional[str] = None
  tags: list[str] = []


def list_datasets(project_dir: Optional[Union[str, pathlib.Path]] = None) -> list[DatasetInfo]:
  """List the datasets in a project directory."""
  project_dir = project_dir or get_project_dir()

  datasets_path = get_datasets_dir(project_dir)

  # Skip if 'datasets' doesn't exist.
  if not os.path.isdir(datasets_path):
    return []

  project_config = read_project_config(project_dir)

  dataset_infos: list[DatasetInfo] = []
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

      dataset_config = get_dataset_config(project_config, namespace, dataset_name)
      tags: list[str] = []
      if dataset_config and dataset_config.settings and dataset_config.settings.tags:
        tags = dataset_config.settings.tags

      dataset_infos.append(DatasetInfo(namespace=namespace, dataset_name=dataset_name, tags=tags))

  return dataset_infos


# TODO(nsthorat): Make this a registry once we have multiple dataset implementations. This breaks a
# circular dependency.
def set_default_dataset_cls(dataset_cls: Type[Dataset]) -> None:
  """Set the default dataset class."""
  global _DEFAULT_DATASET_CLS
  _DEFAULT_DATASET_CLS = dataset_cls
