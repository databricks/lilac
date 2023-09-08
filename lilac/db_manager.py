"""Manages mapping the dataset name to the database instance."""
import os
import pathlib
import threading
from typing import Optional, Type, Union

from pydantic import BaseModel

from .config import get_dataset_config
from .data.dataset import Dataset
from .env import data_path
from .project import read_project_config
from .utils import get_datasets_dir

_DEFAULT_DATASET_CLS: Type[Dataset]

_CACHED_DATASETS: dict[str, Dataset] = {}

_db_lock = threading.Lock()


def get_dataset(namespace: str, dataset_name: str) -> Dataset:
  """Get the dataset instance."""
  if not _DEFAULT_DATASET_CLS:
    raise ValueError('Default dataset class not set.')
  cache_key = f'{namespace}/{dataset_name}'
  # https://docs.pytest.org/en/latest/example/simple.html#pytest-current-test-environment-variable
  inside_test = 'PYTEST_CURRENT_TEST' in os.environ
  with _db_lock:
    if cache_key not in _CACHED_DATASETS or inside_test:
      _CACHED_DATASETS[cache_key] = _DEFAULT_DATASET_CLS(
        namespace=namespace, dataset_name=dataset_name)
    return _CACHED_DATASETS[cache_key]


def remove_dataset_from_cache(namespace: str, dataset_name: str) -> None:
  """Remove the dataset from the db manager cache."""
  cache_key = f'{namespace}/{dataset_name}'
  with _db_lock:
    if cache_key in _CACHED_DATASETS:
      del _CACHED_DATASETS[cache_key]


class DatasetInfo(BaseModel):
  """Information about a dataset."""
  namespace: str
  dataset_name: str
  description: Optional[str] = None
  tags: list[str] = []


def list_datasets(base_dir: Union[str, pathlib.Path]) -> list[DatasetInfo]:
  """List the datasets in a data directory."""
  datasets_path = get_datasets_dir(base_dir)

  # Skip if 'datasets' doesn't exist.
  if not os.path.isdir(datasets_path):
    return []

  project_config = read_project_config(data_path())

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
      tags = []
      if dataset_config:
        tags = dataset_config.tags

      dataset_infos.append(DatasetInfo(namespace=namespace, dataset_name=dataset_name, tags=tags))

  return dataset_infos


# TODO(nsthorat): Make this a registry once we have multiple dataset implementations. This breaks a
# circular dependency.
def set_default_dataset_cls(dataset_cls: Type[Dataset]) -> None:
  """Set the default dataset class."""
  global _DEFAULT_DATASET_CLS
  _DEFAULT_DATASET_CLS = dataset_cls
