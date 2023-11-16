"""Tests for load.py: loading project configs."""

import os
import pathlib
from typing import ClassVar, Iterable, Optional, cast

import numpy as np
import pytest
from distributed import Client
from pytest_mock import MockerFixture
from typing_extensions import override

from .config import Config, DatasetConfig, EmbeddingConfig, SignalConfig
from .data.dataset import DatasetManifest
from .data.dataset_duckdb import DatasetDuckDB
from .db_manager import get_dataset
from .env import set_project_dir
from .load import load
from .project import PROJECT_CONFIG_FILENAME, init
from .schema import EMBEDDING_KEY, Field, Item, RichData, field, lilac_embedding, schema
from .signal import TextEmbeddingSignal, TextSignal, clear_signal_registry, register_signal
from .source import Source, SourceSchema, clear_source_registry, register_source
from .tasks import TaskManager
from .utils import to_yaml

SIMPLE_ITEMS: list[Item] = [
  {'str': 'a', 'int': 1, 'bool': False, 'float': 3.0},
  {'str': 'b', 'int': 2, 'bool': True, 'float': 2.0},
  {'str': 'c', 'int': 3, 'bool': True, 'float': 1.0},
]

EMBEDDINGS: list[tuple[str, list[float]]] = [
  ('a', [1.0, 0.0, 0.0]),
  ('b', [1.0, 1.0, 0.0]),
  ('c', [1.0, 1.0, 0.0]),
]

STR_EMBEDDINGS: dict[str, list[float]] = {text: embedding for text, embedding in EMBEDDINGS}


@pytest.fixture(scope='session')
def task_manager() -> TaskManager:
  return TaskManager(Client(processes=False))


class TestSource(Source):
  """A test source."""

  name: ClassVar[str] = 'test_source'

  @override
  def source_schema(self) -> SourceSchema:
    """Yield all items."""
    return SourceSchema(
      fields={
        'str': field('string'),
        'int': field('int32'),
        'bool': field('boolean'),
        'float': field('float32'),
      },
      num_items=len(SIMPLE_ITEMS),
    )

  @override
  def yield_items(self) -> Iterable[Item]:
    """Yield all items."""
    yield from SIMPLE_ITEMS


class TestEmbedding(TextEmbeddingSignal):
  """A test embed function."""

  name: ClassVar[str] = 'test_embedding'

  @override
  def compute(self, data: Iterable[RichData]) -> Iterable[Item]:
    """Call the embedding function."""
    for example in data:
      yield [lilac_embedding(0, len(example), np.array(STR_EMBEDDINGS[cast(str, example)]))]


class TestSignal(TextSignal):
  name: ClassVar[str] = 'test_signal'

  _call_count: int = 0

  def fields(self) -> Field:
    return field('int32')

  def compute(self, data: Iterable[RichData]) -> Iterable[Optional[Item]]:
    for text_content in data:
      self._call_count += 1
      yield len(text_content)


@pytest.fixture(scope='module', autouse=True)
def setup_teardown() -> Iterable[None]:
  # Setup.
  register_source(TestSource)
  register_signal(TestSignal)
  register_signal(TestEmbedding)

  # Unit test runs.
  yield

  # Teardown.
  clear_source_registry()
  clear_signal_registry()


def test_load_config_obj(tmp_path: pathlib.Path, task_manager: TaskManager) -> None:
  set_project_dir(tmp_path)

  # Initialize the lilac project. init() defaults to the project directory.
  init()

  project_config = Config(
    datasets=[DatasetConfig(namespace='namespace', name='test', source=TestSource())]
  )

  # Load the project config from a config object.
  load(config=project_config, task_manager=task_manager)

  dataset = get_dataset('namespace', 'test')

  assert dataset.manifest() == DatasetManifest(
    namespace='namespace',
    dataset_name='test',
    data_schema=schema({'str': 'string', 'int': 'int32', 'bool': 'boolean', 'float': 'float32'}),
    num_items=3,
    source=TestSource(),
  )


def test_load_project_config_yml(tmp_path: pathlib.Path, task_manager: TaskManager) -> None:
  set_project_dir(tmp_path)

  # Initialize the lilac project. init() defaults to the project directory.
  init()

  # Simulate the user manually editing the project config.
  project_config = Config(
    datasets=[DatasetConfig(namespace='namespace', name='test', source=TestSource())]
  )
  project_config_yml = to_yaml(project_config.model_dump())
  config_path = os.path.join(tmp_path, PROJECT_CONFIG_FILENAME)

  # Write the project_config as yml to project dir.
  with open(config_path, 'w') as f:
    f.write(project_config_yml)

  load(config=config_path, task_manager=task_manager)

  dataset = get_dataset('namespace', 'test')

  assert dataset.manifest() == DatasetManifest(
    namespace='namespace',
    dataset_name='test',
    data_schema=schema({'str': 'string', 'int': 'int32', 'bool': 'boolean', 'float': 'float32'}),
    num_items=3,
    source=TestSource(),
  )


def test_load_config_yml_outside_project(tmp_path: pathlib.Path, task_manager: TaskManager) -> None:
  # This test makes sure that we can load a yml file from outside the project directory.

  config_path = os.path.join(tmp_path, PROJECT_CONFIG_FILENAME)
  project_dir = os.path.join(tmp_path, 'project')
  os.makedirs(project_dir)
  set_project_dir(tmp_path)

  project_config = Config(
    datasets=[DatasetConfig(namespace='namespace', name='test', source=TestSource())]
  )

  project_config_yml = to_yaml(project_config.model_dump())

  # Write the project_config as yml to project dir.
  with open(config_path, 'w') as f:
    f.write(project_config_yml)

  load(config=config_path, task_manager=task_manager)

  dataset = get_dataset('namespace', 'test')

  assert dataset.manifest() == DatasetManifest(
    namespace='namespace',
    dataset_name='test',
    data_schema=schema({'str': 'string', 'int': 'int32', 'bool': 'boolean', 'float': 'float32'}),
    num_items=3,
    source=TestSource(),
  )


def test_load_signals(tmp_path: pathlib.Path, task_manager: TaskManager) -> None:
  set_project_dir(tmp_path)

  # Initialize the lilac project. init() defaults to the project directory.
  init()

  test_signal = TestSignal()
  project_config = Config(
    datasets=[
      DatasetConfig(
        namespace='namespace',
        name='test',
        source=TestSource(),
        signals=[SignalConfig(path=('str',), signal=test_signal)],
      )
    ]
  )

  # Load the project config from a config object.
  load(config=project_config, task_manager=task_manager)

  dataset = get_dataset('namespace', 'test')

  assert dataset.manifest() == DatasetManifest(
    namespace='namespace',
    dataset_name='test',
    data_schema=schema(
      {
        'str': field(
          'string', fields={'test_signal': field('int32', signal=test_signal.model_dump())}
        ),
        'int': 'int32',
        'bool': 'boolean',
        'float': 'float32',
      }
    ),
    num_items=3,
    source=TestSource(),
  )


def test_load_embeddings(tmp_path: pathlib.Path, task_manager: TaskManager) -> None:
  set_project_dir(tmp_path)

  # Initialize the lilac project. init() defaults to the project directory.
  init()

  project_config = Config(
    datasets=[
      DatasetConfig(
        namespace='namespace',
        name='test',
        source=TestSource(),
        embeddings=[EmbeddingConfig(path=('str',), embedding='test_embedding')],
      )
    ]
  )

  # Load the project config from a config object.
  load(config=project_config, task_manager=task_manager)

  dataset = get_dataset('namespace', 'test')

  assert dataset.manifest() == DatasetManifest(
    namespace='namespace',
    dataset_name='test',
    data_schema=schema(
      {
        'str': field(
          'string',
          fields={
            'test_embedding': field(
              signal=TestEmbedding().model_dump(),
              fields=[field('string_span', fields={EMBEDDING_KEY: 'embedding'})],
            )
          },
        ),
        'int': 'int32',
        'bool': 'boolean',
        'float': 'float32',
      }
    ),
    num_items=3,
    source=TestSource(),
  )


def test_load_twice_no_overwrite(
  tmp_path: pathlib.Path, task_manager: TaskManager, mocker: MockerFixture
) -> None:
  set_project_dir(tmp_path)

  # Initialize the lilac project. init() defaults to the project directory.
  init()

  compute_signal_mock = mocker.spy(DatasetDuckDB, DatasetDuckDB.compute_signal.__name__)
  compute_embedding_mock = mocker.spy(DatasetDuckDB, DatasetDuckDB.compute_embedding.__name__)

  test_signal = TestSignal()
  project_config = Config(
    datasets=[
      DatasetConfig(
        namespace='namespace',
        name='test',
        source=TestSource(),
        signals=[SignalConfig(path=('str',), signal=test_signal)],
        embeddings=[EmbeddingConfig(path=('str',), embedding='test_embedding')],
      )
    ]
  )

  # Load the project config from a config object.
  load(config=project_config, task_manager=task_manager)

  assert compute_signal_mock.call_count == 1
  assert compute_embedding_mock.call_count == 1

  first_manifest = get_dataset('namespace', 'test').manifest()

  # Load the project again, make sure signals and embeddings are not computed again.
  load(config=project_config, task_manager=task_manager)

  assert compute_signal_mock.call_count == 1
  assert compute_embedding_mock.call_count == 1

  second_manifest = get_dataset('namespace', 'test').manifest()

  assert first_manifest == second_manifest


def test_load_twice_overwrite(
  tmp_path: pathlib.Path, task_manager: TaskManager, mocker: MockerFixture
) -> None:
  set_project_dir(tmp_path)

  # Initialize the lilac project. init() defaults to the project directory.
  init()

  compute_signal_mock = mocker.spy(DatasetDuckDB, DatasetDuckDB.compute_signal.__name__)
  compute_embedding_mock = mocker.spy(DatasetDuckDB, DatasetDuckDB.compute_embedding.__name__)

  test_signal = TestSignal()
  project_config = Config(
    datasets=[
      DatasetConfig(
        namespace='namespace',
        name='test',
        source=TestSource(),
        signals=[SignalConfig(path=('str',), signal=test_signal)],
        embeddings=[EmbeddingConfig(path=('str',), embedding='test_embedding')],
      )
    ]
  )

  # Load the project config from a config object.
  load(config=project_config, task_manager=task_manager)

  assert compute_signal_mock.call_count == 1
  assert compute_embedding_mock.call_count == 1

  first_manifest = get_dataset('namespace', 'test').manifest()

  # Load the project again, make sure signals and embeddings are not computed again.
  load(config=project_config, task_manager=task_manager, overwrite=True)

  # With overwrite=True, compute_signal and compute_embedding should be called again.
  assert compute_signal_mock.call_count == 2
  assert compute_embedding_mock.call_count == 2

  second_manifest = get_dataset('namespace', 'test').manifest()

  assert first_manifest == second_manifest
