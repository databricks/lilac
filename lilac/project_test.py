"""Tests for server.py."""

import os
from typing import Iterable

import pytest
from typing_extensions import override

from ..source import Source, SourceSchema
from .env import data_path
from .project import PROJECT_CONFIG_FILENAME, create_project_and_set_env
from .schema import Item, schema


async def test_create_project_and_set_env(tmp_path_factory: pytest.TempPathFactory) -> None:
  tmp_path = str(tmp_path_factory.mktemp('test_project'))

  # Test that it creates a project if it doesn't exist.
  create_project_and_set_env(tmp_path)

  assert os.path.exists(os.path.join(tmp_path, PROJECT_CONFIG_FILENAME))
  assert data_path() == tmp_path


async def test_create_project_and_set_env_from_env(
    tmp_path_factory: pytest.TempPathFactory) -> None:
  tmp_path = str(tmp_path_factory.mktemp('test_project'))

  os.environ['LILAC_DATA_PATH'] = tmp_path

  # Test that an empty project path defaults to the data path.
  create_project_and_set_env(project_path_arg='')

  assert os.path.exists(os.path.join(tmp_path, PROJECT_CONFIG_FILENAME))
  assert data_path() == tmp_path


class TestSource(Source):
  """A test source."""
  name = 'test_source'

  @override
  def setup(self) -> None:
    pass

  @override
  def source_schema(self) -> SourceSchema:
    """Return the source schema."""
    return SourceSchema(fields=schema({'x': 'int64', 'y': 'string'}).fields, num_items=2)

  @override
  def process(self) -> Iterable[Item]:
    return [{'x': 1, 'y': 'ten'}, {'x': 2, 'y': 'twenty'}]
