"""Fixtures for dataset tests."""
import pathlib
from typing import Generator, Optional, Type

import pytest

from ..config import CONFIG
from ..schema import Item, Schema
from .dataset import Dataset
from .dataset_duckdb import DatasetDuckDB
from .dataset_test_utils import make_dataset


@pytest.fixture(scope='function', params=[DatasetDuckDB])
def make_test_data(tmp_path: pathlib.Path, request: pytest.FixtureRequest) -> Generator:
  """A pytest fixture for creating temporary test datasets."""
  data_path = CONFIG['LILAC_DATA_PATH']
  CONFIG['LILAC_DATA_PATH'] = str(tmp_path)
  dataset_cls: Type[Dataset] = request.param

  def _make_test_data(items: list[Item], schema: Optional[Schema] = None) -> Dataset:
    return make_dataset(dataset_cls, tmp_path, items, schema)

  # Return the factory for datasets that test methods can use.
  yield _make_test_data

  # Teardown.
  CONFIG['LILAC_DATA_PATH'] = data_path or ''
