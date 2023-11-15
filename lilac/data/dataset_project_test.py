"""Implementation-agnostic tests of the Dataset DB API working with projects."""

from pathlib import Path
from typing import ClassVar, Iterable, Optional, cast

import numpy as np
import pytest
from typing_extensions import override

from ..config import (
  Config,
  DatasetConfig,
  DatasetSettings,
  DatasetUISettings,
  EmbeddingConfig,
  SignalConfig,
)
from ..db_manager import get_dataset
from ..env import get_project_dir
from ..load_dataset import create_dataset
from ..project import create_project_and_set_env, read_project_config
from ..schema import Field, Item, RichData, field, lilac_embedding
from ..signal import TextEmbeddingSignal, TextSignal, clear_signal_registry, register_signal
from ..source import Source, SourceSchema, clear_source_registry, register_source

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


@pytest.fixture(scope='function', autouse=True)
def setup_data_dir(tmp_path: Path) -> None:
  create_project_and_set_env(str(tmp_path))

  dataset_config = DatasetConfig(namespace='namespace', name='test', source=TestSource())
  create_dataset(dataset_config)


def test_load_dataset_updates_project() -> None:
  config = read_project_config(get_project_dir())

  assert config == Config(
    datasets=[
      DatasetConfig(
        namespace='namespace',
        name='test',
        source=TestSource(),
        # Settings are automatically computed when not provided.
        settings=DatasetSettings(ui=DatasetUISettings(media_paths=[('str',)], markdown_paths=[])),
      )
    ]
  )


def test_delete_dataset_updates_project() -> None:
  config = read_project_config(get_project_dir())

  # TODO: nsthorat do this.
  pass


def test_compute_signal_updates_project() -> None:
  dataset = get_dataset('namespace', 'test')
  dataset.compute_signal(TestSignal(), path='str')

  config = read_project_config(get_project_dir())

  assert config == Config(
    datasets=[
      DatasetConfig(
        namespace='namespace',
        name='test',
        source=TestSource(),
        # Settings are automatically computed when not provided.
        settings=DatasetSettings(ui=DatasetUISettings(media_paths=[('str',)], markdown_paths=[])),
        signals=[SignalConfig(path=('str',), signal=TestSignal())],
      )
    ]
  )


def test_delete_signal_updates_project() -> None:
  dataset = get_dataset('namespace', 'test')
  dataset.compute_signal(TestSignal(), path='str')

  config = read_project_config(get_project_dir())

  assert config == Config(
    datasets=[
      DatasetConfig(
        namespace='namespace',
        name='test',
        source=TestSource(),
        # Settings are automatically computed when not provided.
        settings=DatasetSettings(ui=DatasetUISettings(media_paths=[('str',)], markdown_paths=[])),
        signals=[SignalConfig(path=('str',), signal=TestSignal())],
      )
    ]
  )

  dataset.delete_signal(signal_path=('str', TestSignal.name))

  config = read_project_config(get_project_dir())

  assert config == Config(
    datasets=[
      DatasetConfig(
        namespace='namespace',
        name='test',
        source=TestSource(),
        # Settings are automatically computed when not provided.
        settings=DatasetSettings(ui=DatasetUISettings(media_paths=[('str',)], markdown_paths=[])),
        # Signals should be deleted.
        signals=[],
      )
    ]
  )


def test_compute_embedding_updates_project() -> None:
  dataset = get_dataset('namespace', 'test')
  dataset.compute_embedding('test_embedding', path='str')

  config = read_project_config(get_project_dir())

  assert config == Config(
    datasets=[
      DatasetConfig(
        namespace='namespace',
        name='test',
        source=TestSource(),
        # Settings are automatically computed when not provided.
        settings=DatasetSettings(ui=DatasetUISettings(media_paths=[('str',)], markdown_paths=[])),
        embeddings=[EmbeddingConfig(path=('str',), embedding='test_embedding')],
      )
    ]
  )
