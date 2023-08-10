"""Manages mapping the dataset name to the database instance."""
import os
import pathlib
import threading
from typing import Optional, Type, Union

import yaml
from pydantic import BaseModel

from .config import DatasetConfig
from .data.dataset import Dataset
from .data.dataset_duckdb import get_config_filepath
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

      # Open the config file to read the tags. We avoid instantiating a dataset for now to reduce
      # the overhead of listing datasets.
      config_filepath = get_config_filepath(namespace, dataset_name)
      tags = []
      if os.path.exists(config_filepath):
        with open(config_filepath) as f:
          config = DatasetConfig(**yaml.safe_load(f))
        tags = config.tags

      dataset_infos.append(DatasetInfo(namespace=namespace, dataset_name=dataset_name, tags=tags))

  return dataset_infos


# TODO(nsthorat): Make this a registry once we have multiple dataset implementations. This breaks a
# circular dependency.
def set_default_dataset_cls(dataset_cls: Type[Dataset]) -> None:
  """Set the default dataset class."""
  global _DEFAULT_DATASET_CLS
  _DEFAULT_DATASET_CLS = dataset_cls
