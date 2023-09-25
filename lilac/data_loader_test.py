"""Tests for data_loader.py."""

import os
import pathlib
import uuid
from typing import ClassVar, Iterable

import pytest
from pytest_mock import MockerFixture
from typing_extensions import override

from lilac.sources.source_registry import clear_source_registry, register_source

from .config import Config, DatasetConfig, DatasetSettings, DatasetUISettings
from .data.dataset import SourceManifest
from .data.dataset_duckdb import read_source_manifest
from .data.dataset_utils import parquet_filename
from .data_loader import process_source
from .project import read_project_config
from .schema import PARQUET_FILENAME_PREFIX, ROWID, Item, schema
from .source import Source, SourceSchema
from .test_utils import fake_uuid, read_items
from .utils import DATASETS_DIR_NAME


class TestSource(Source):
  """A test source."""
  name: ClassVar[str] = 'test_source'

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


@pytest.fixture(scope='module', autouse=True)
def setup_teardown() -> Iterable[None]:
  # Setup.
  register_source(TestSource)
  # Unit test runs.
  yield
  # Teardown.
  clear_source_registry()


def test_data_loader(tmp_path: pathlib.Path, mocker: MockerFixture) -> None:
  mocker.patch.dict(os.environ, {'LILAC_PROJECT_DIR': str(tmp_path)})

  mock_uuid = mocker.patch.object(uuid, 'uuid4', autospec=True)
  mock_uuid.side_effect = [fake_uuid(b'1'), fake_uuid(b'2')]

  source = TestSource()
  setup_mock = mocker.spy(TestSource, 'setup')

  output_dir, num_items = process_source(
    tmp_path, DatasetConfig(namespace='test_namespace', name='test_dataset', source=source))

  assert setup_mock.call_count == 1

  assert output_dir == os.path.join(tmp_path, DATASETS_DIR_NAME, 'test_namespace', 'test_dataset')
  assert num_items == 2

  source_manifest = read_source_manifest(output_dir)

  assert source_manifest == SourceManifest(
    files=[parquet_filename(PARQUET_FILENAME_PREFIX, 0, 1)],
    data_schema=schema({
      'x': 'int64',
      'y': 'string'
    }),
    source=source)

  items = read_items(output_dir, source_manifest.files, source_manifest.data_schema)

  assert items == [{
    ROWID: fake_uuid(b'1').hex,
    'x': 1,
    'y': 'ten'
  }, {
    ROWID: fake_uuid(b'2').hex,
    'x': 2,
    'y': 'twenty'
  }]

  project_config = read_project_config(str(tmp_path))
  assert project_config == Config(datasets=[
    DatasetConfig(
      namespace='test_namespace',
      name='test_dataset',
      source=source,
      # 'y' is the longest path, so should be set as the default setting.
      settings=DatasetSettings(ui=DatasetUISettings(media_paths=[('y',)])))
  ])
