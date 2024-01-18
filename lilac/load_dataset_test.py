"""Tests for load_dataset.py."""

import os
import pathlib
import uuid
from typing import ClassVar, Iterable, Optional, Type

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from datasets import Dataset, DatasetDict
from pytest_mock import MockerFixture
from typing_extensions import override

from .config import Config, DatasetConfig, DatasetSettings, DatasetUISettings
from .data.dataset import SortOrder
from .data.dataset_duckdb import read_source_manifest
from .data.dataset_utils import get_parquet_filename, schema_to_arrow_schema
from .load_dataset import from_dicts, from_huggingface, process_source
from .project import read_project_config
from .schema import PARQUET_FILENAME_PREFIX, ROWID, STRING, Field, Item, Schema, schema
from .source import Source, SourceManifest, SourceSchema, clear_source_registry, register_source
from .tasks import TaskId
from .test_utils import fake_uuid, retrieve_parquet_rows
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
  def yield_items(self) -> Iterable[Item]:
    return [{'x': 1, 'y': 'ten'}, {'x': 2, 'y': 'twenty'}]


class TestFastSource(Source):
  """A fast test source."""

  name: ClassVar[str] = 'test_fast_source'

  @override
  def setup(self) -> None:
    pass

  @override
  def source_schema(self) -> SourceSchema:
    """Return the source schema."""
    return SourceSchema(fields=schema({'x': 'int64', 'y': 'string'}).fields, num_items=2)

  @override
  def load_to_parquet(self, output_dir: str, task_id: Optional[TaskId] = None) -> SourceManifest:
    rows = [
      {ROWID: fake_uuid(b'1').hex, 'x': 1, 'y': 'ten'},
      {ROWID: fake_uuid(b'2').hex, 'x': 2, 'y': 'twenty'},
    ]
    schema = Schema(fields=self.source_schema().fields.copy())
    schema.fields[ROWID] = Field(dtype=STRING)

    arrow_schema = schema_to_arrow_schema(schema)
    table = pa.Table.from_pylist(rows, schema=arrow_schema)

    filename = get_parquet_filename(PARQUET_FILENAME_PREFIX, 0, 1)
    out_file = os.path.join(output_dir, filename)
    os.makedirs(output_dir, exist_ok=True)
    pq.write_table(table, out_file)

    return SourceManifest(
      files=[filename], data_schema=Schema(fields=self.source_schema().fields), source=self
    )


@pytest.fixture(scope='module', autouse=True)
def setup_teardown() -> Iterable[None]:
  # Setup.
  register_source(TestSource)
  register_source(TestFastSource)
  # Unit test runs.
  yield
  # Teardown.
  clear_source_registry()


@pytest.fixture(autouse=True)
def set_project_dir(tmp_path: pathlib.Path, mocker: MockerFixture) -> None:
  mocker.patch.dict(os.environ, {'LILAC_PROJECT_DIR': str(tmp_path)})


@pytest.mark.parametrize('source_cls', [TestSource, TestFastSource])
def test_data_loader(
  source_cls: Type[Source], tmp_path: pathlib.Path, mocker: MockerFixture
) -> None:
  mock_uuid = mocker.patch.object(uuid, 'uuid4', autospec=True)
  mock_uuid.side_effect = [fake_uuid(b'1'), fake_uuid(b'2')]

  source = source_cls()
  setup_mock = mocker.spy(source_cls, 'setup')

  output_dir = process_source(
    tmp_path,
    DatasetConfig(namespace='test_namespace', name='test_dataset', source=source),
  )

  assert setup_mock.call_count == 1

  assert output_dir == os.path.join(tmp_path, DATASETS_DIR_NAME, 'test_namespace', 'test_dataset')

  source_manifest = read_source_manifest(output_dir)

  assert source_manifest == SourceManifest(
    files=[get_parquet_filename(PARQUET_FILENAME_PREFIX, 0, 1)],
    data_schema=schema({'x': 'int64', 'y': 'string'}),
    source=source,
  )

  items = retrieve_parquet_rows(pathlib.Path(output_dir), source_manifest, retain_rowid=True)

  assert items == [
    {ROWID: fake_uuid(b'1').hex, 'x': 1, 'y': 'ten'},
    {ROWID: fake_uuid(b'2').hex, 'x': 2, 'y': 'twenty'},
  ]

  project_config = read_project_config(str(tmp_path))
  assert project_config == Config(
    datasets=[
      DatasetConfig(
        namespace='test_namespace',
        name='test_dataset',
        source=source,
        # 'y' is the longest path, so should be set as the default setting.
        settings=DatasetSettings(ui=DatasetUISettings(media_paths=[('y',)])),
      )
    ]
  )


def test_from_dicts() -> None:
  items = [{'text': 'hello'}, {'text': 'world'}]
  ds = from_dicts('local', 'test', items)
  assert list(ds.select_rows(sort_by=['text'], sort_order=SortOrder.ASC)) == items


def test_from_hf_dataset() -> None:
  def gen() -> Iterable[dict[str, str]]:
    yield {'text': 'hello'}
    yield {'text': 'world'}

  hf_ds = Dataset.from_generator(gen)
  ds = from_huggingface(hf_ds)
  assert list(ds.select_rows(sort_by=['text'], sort_order=SortOrder.ASC)) == [
    {'__hfsplit__': 'default', 'text': 'hello'},
    {'__hfsplit__': 'default', 'text': 'world'},
  ]
  assert ds.namespace == 'local'
  assert ds.dataset_name == 'generator'


def test_from_hf_dataset_dict() -> None:
  def gen() -> Iterable[dict[str, str]]:
    yield {'text': 'hello'}
    yield {'text': 'world'}

  hf_ds_dict = DatasetDict({'train': Dataset.from_generator(gen)})
  ds = from_huggingface(hf_ds_dict)
  assert list(ds.select_rows(sort_by=['text'], sort_order=SortOrder.ASC)) == [
    {'__hfsplit__': 'train', 'text': 'hello'},
    {'__hfsplit__': 'train', 'text': 'world'},
  ]
  assert ds.namespace == 'local'
  assert ds.dataset_name == 'generator'


def test_from_hf_explicit_namespace_and_name() -> None:
  def gen() -> Iterable[dict[str, str]]:
    yield {'text': 'hello'}
    yield {'text': 'world'}

  hf_ds = Dataset.from_generator(gen)
  ds = from_huggingface(hf_ds, namespace='local', name='test')
  assert list(ds.select_rows(sort_by=['text'], sort_order=SortOrder.ASC)) == [
    {'__hfsplit__': 'default', 'text': 'hello'},
    {'__hfsplit__': 'default', 'text': 'world'},
  ]
  assert ds.namespace == 'local'
  assert ds.dataset_name == 'test'
