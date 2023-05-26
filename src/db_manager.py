"""Manages mapping the dataset name to the database instance."""
import os

from .data.dataset import Dataset
from .data.dataset_duckdb import DatasetDuckDB

_CACHED_DATASETS: dict[str, Dataset] = {}


def get_dataset(namespace: str, dataset_name: str) -> Dataset:
  """Get the dataset instance."""
  cache_key = f'{namespace}/{dataset_name}'
  # https://docs.pytest.org/en/latest/example/simple.html#pytest-current-test-environment-variable
  inside_test = 'PYTEST_CURRENT_TEST' in os.environ
  if cache_key not in _CACHED_DATASETS or inside_test:
    _CACHED_DATASETS[cache_key] = DatasetDuckDB(namespace=namespace, dataset_name=dataset_name)
  return _CACHED_DATASETS[cache_key]
