"""Manages mapping the dataset name to the database instance."""

from .data.db_dataset import DatasetDB
from .data.db_dataset_duckdb import DatasetDuckDB

_DATASET_DBS: dict[str, DatasetDB] = {}


def get_dataset_db(namespace: str, dataset_name: str) -> DatasetDB:
  """Get the dataset database instance for the dataset."""
  cache_key = f'{namespace}/{dataset_name}'
  if cache_key not in _DATASET_DBS:
    _DATASET_DBS[cache_key] = DatasetDuckDB(namespace=namespace, dataset_name=dataset_name)
  return _DATASET_DBS[cache_key]
