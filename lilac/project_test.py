"""Tests for server.py."""

import os

import pytest

from .env import data_path
from .project import PROJECT_CONFIG_FILENAME, create_project_and_set_env


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
