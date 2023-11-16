"""Tests for dataset.config()."""

from typing import ClassVar, Iterable, Optional

import numpy as np
import pytest
from typing_extensions import override

from ..config import (
  DatasetConfig,
  DatasetSettings,
  DatasetUISettings,
  EmbeddingConfig,
  SignalConfig,
)
from ..schema import Field, Item, RichData, field, lilac_embedding
from ..signal import TextEmbeddingSignal, TextSignal, clear_signal_registry, register_signal
from ..source import clear_source_registry, register_source
from .dataset_test_utils import TestDataMaker, TestSource


class TestSignal(TextSignal):
  name: ClassVar[str] = 'test_signal'

  @override
  def fields(self) -> Field:
    return field(fields={'len': 'int32'})

  @override
  def compute(self, data: Iterable[RichData]) -> Iterable[Optional[Item]]:
    return [{'len': len(text_content)} for text_content in data]


class TestSignal2(TextSignal):
  name: ClassVar[str] = 'test_signal2'

  @override
  def fields(self) -> Field:
    return field(fields={'len2': 'int32'})

  @override
  def compute(self, data: Iterable[RichData]) -> Iterable[Optional[Item]]:
    return [{'len2': len(text_content)} for text_content in data]


class TestEmbedding(TextEmbeddingSignal):
  """A test embed function."""

  name: ClassVar[str] = 'test_embedding'

  @override
  def compute(self, data: Iterable[RichData]) -> Iterable[Item]:
    """Call the embedding function."""
    for example in data:
      yield [lilac_embedding(0, len(example), np.array([1.0]))]


class TestEmbedding2(TextEmbeddingSignal):
  """A test embed function."""

  name: ClassVar[str] = 'test_embedding2'

  @override
  def compute(self, data: Iterable[RichData]) -> Iterable[Item]:
    """Call the embedding function."""
    for example in data:
      yield [lilac_embedding(0, len(example), np.array([2.0]))]


@pytest.fixture(scope='module', autouse=True)
def setup_teardown() -> Iterable[None]:
  # Setup.
  clear_signal_registry()
  register_source(TestSource)
  register_signal(TestSignal)
  register_signal(TestSignal2)
  register_signal(TestEmbedding)
  register_signal(TestEmbedding2)

  # Unit test runs.
  yield
  # Teardown.
  clear_source_registry()
  clear_signal_registry()


def test_config_compute_signal(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data([{'text': 'hello'}, {'text': 'hello world'}])

  assert dataset.config() == DatasetConfig(
    namespace='test_namespace',
    name='test_dataset',
    source=TestSource(),
    # 'text' is the longest path, so should be set as the default setting.
    settings=DatasetSettings(ui=DatasetUISettings(media_paths=[('text',)])),
  )

  dataset.compute_signal(TestSignal(), 'text')

  assert dataset.config() == DatasetConfig(
    namespace='test_namespace',
    name='test_dataset',
    source=TestSource(),
    signals=[SignalConfig(path=('text',), signal=TestSignal())],
    settings=DatasetSettings(ui=DatasetUISettings(media_paths=[('text',)])),
  )

  # Computing the same signal again should not change the config.
  dataset.compute_signal(TestSignal(), 'text', overwrite=True)

  assert dataset.config() == DatasetConfig(
    namespace='test_namespace',
    name='test_dataset',
    source=TestSource(),
    signals=[SignalConfig(path=('text',), signal=TestSignal())],
    settings=DatasetSettings(ui=DatasetUISettings(media_paths=[('text',)])),
  )

  # Computing another signal should add another config.
  dataset.compute_signal(TestSignal2(), 'text')

  assert dataset.config() == DatasetConfig(
    namespace='test_namespace',
    name='test_dataset',
    source=TestSource(),
    signals=[
      SignalConfig(path=('text',), signal=TestSignal()),
      SignalConfig(path=('text',), signal=TestSignal2()),
    ],
    settings=DatasetSettings(ui=DatasetUISettings(media_paths=[('text',)])),
  )


def test_config_compute_embedding(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data([{'text': 'hello'}, {'text': 'hello world'}])

  assert dataset.config() == DatasetConfig(
    namespace='test_namespace',
    name='test_dataset',
    source=TestSource(),
    # 'text' is the longest path, so should be set as the default setting.
    settings=DatasetSettings(ui=DatasetUISettings(media_paths=[('text',)])),
  )

  dataset.compute_embedding('test_embedding', 'text')

  assert dataset.config() == DatasetConfig(
    namespace='test_namespace',
    name='test_dataset',
    source=TestSource(),
    embeddings=[EmbeddingConfig(path=('text',), embedding='test_embedding')],
    settings=DatasetSettings(ui=DatasetUISettings(media_paths=[('text',)])),
  )

  # Computing the same embedding again should not change the config.
  dataset.compute_embedding('test_embedding', 'text')

  assert dataset.config() == DatasetConfig(
    namespace='test_namespace',
    name='test_dataset',
    source=TestSource(),
    embeddings=[EmbeddingConfig(path=('text',), embedding='test_embedding')],
    settings=DatasetSettings(ui=DatasetUISettings(media_paths=[('text',)])),
  )

  # Computing another embedding should add another config.
  dataset.compute_embedding('test_embedding2', 'text')

  assert dataset.config() == DatasetConfig(
    namespace='test_namespace',
    name='test_dataset',
    source=TestSource(),
    embeddings=[
      EmbeddingConfig(path=('text',), embedding='test_embedding'),
      EmbeddingConfig(path=('text',), embedding='test_embedding2'),
    ],
    settings=DatasetSettings(ui=DatasetUISettings(media_paths=[('text',)])),
  )


def test_settings(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data([{'text': 'hello'}, {'text': 'hello world'}])
  expected_settings = DatasetSettings(ui=DatasetUISettings(media_paths=[('text',)]))

  # Settings is reflected in the config and the public settings method.
  assert dataset.config() == DatasetConfig(
    namespace='test_namespace', name='test_dataset', source=TestSource(), settings=expected_settings
  )

  assert dataset.settings() == expected_settings

  # Settings can only be updated through the public method for updating settings.
  dataset.update_settings(DatasetSettings(ui=DatasetUISettings(media_paths=[('str',)])))

  expected_settings = DatasetSettings(ui=DatasetUISettings(media_paths=[('str',)]))
  assert dataset.settings() == expected_settings
  assert dataset.config() == DatasetConfig(
    namespace='test_namespace', name='test_dataset', source=TestSource(), settings=expected_settings
  )
