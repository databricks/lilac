"""Fixtures for dataset tests."""
import os
import pathlib
from typing import Generator, Optional, Type

import freezegun.config
import pytest
from pytest_mock import MockerFixture

from .data.dataset import Dataset
from .data.dataset_duckdb import DatasetDuckDB
from .data.dataset_test_utils import TestProcessLogger, make_dataset
from .db_manager import set_default_dataset_cls
from .schema import Item, Schema

# Fixes https://github.com/huggingface/transformers/issues/24545
freezegun.config.configure(extend_ignore_list=['transformers', 'torch'])


@pytest.fixture(scope='function', params=[DatasetDuckDB])
def make_test_data(
  tmp_path: pathlib.Path, mocker: MockerFixture, request: pytest.FixtureRequest
) -> Generator:
  """A pytest fixture for creating temporary test datasets."""
  mocker.patch.dict(os.environ, {'LILAC_PROJECT_DIR': str(tmp_path)})
  dataset_cls: Type[Dataset] = request.param
  set_default_dataset_cls(dataset_cls)

  def _make_test_data(items: list[Item], schema: Optional[Schema] = None) -> Dataset:
    return make_dataset(dataset_cls, tmp_path, items, schema)

  # Return the factory for datasets that test methods can use.
  yield _make_test_data


@pytest.fixture(scope='function')
def test_process_logger(tmp_path: pathlib.Path) -> Generator:
  """A pytest fixture for creating a logger that can be read between workers and the scheduler."""
  # Return the factory for datasets that test methods can use.
  yield TestProcessLogger(tmp_path)
