"""Manages mapping the dataset name to the database instance."""
import os
import threading
from typing import Type

from .data.dataset import Dataset

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


# TODO(nsthorat): Make this a registry once we have multiple dataset implementations. This breaks a
# circular dependency.
def set_default_dataset_cls(dataset_cls: Type[Dataset]) -> None:
  """Set the default dataset class."""
  global _DEFAULT_DATASET_CLS
  _DEFAULT_DATASET_CLS = dataset_cls
