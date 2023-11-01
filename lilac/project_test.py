"""Tests for server.py."""

import os
import pathlib

import pytest

from .config import Config
from .env import get_project_dir, set_project_dir
from .project import PROJECT_CONFIG_FILENAME, create_project_and_set_env, init, read_project_config


async def test_create_project_and_set_env(tmp_path_factory: pytest.TempPathFactory) -> None:
  tmp_path = str(tmp_path_factory.mktemp('test_project'))

  # Test that it creates a project if it doesn't exist.
  create_project_and_set_env(tmp_path)

  assert os.path.exists(os.path.join(tmp_path, PROJECT_CONFIG_FILENAME))
  assert get_project_dir() == tmp_path


async def test_create_project_and_set_env_from_env(
  tmp_path_factory: pytest.TempPathFactory
) -> None:
  tmp_path = str(tmp_path_factory.mktemp('test_project'))

  os.environ['LILAC_PROJECT_DIR'] = tmp_path

  # Test that an empty project directory defaults to the data path.
  create_project_and_set_env(project_dir_arg='')

  assert os.path.exists(os.path.join(tmp_path, PROJECT_CONFIG_FILENAME))
  assert get_project_dir() == tmp_path


def test_init(tmp_path: pathlib.Path) -> None:
  set_project_dir(tmp_path)

  # Initialize the lilac project. init() defaults to the project directory.
  init()

  assert read_project_config(tmp_path) == Config(datasets=[])
