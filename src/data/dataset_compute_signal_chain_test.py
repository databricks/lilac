"""Tests for dataset.compute_signal() when signals are chained."""

import re
from typing import Iterable, List, Optional, cast

import numpy as np
import pytest
from pytest_mock import MockerFixture
from typing_extensions import override

from ..embeddings.vector_store import VectorStore
from ..schema import (
  UUID_COLUMN,
  VALUE_KEY,
  Field,
  Item,
  RichData,
  VectorKey,
  field,
  schema,
  signal_field,
)
from ..signals.signal import (
  Signal,
  TextEmbeddingModelSignal,
  TextEmbeddingSignal,
  TextSignal,
  TextSplitterSignal,
  clear_signal_registry,
  register_signal,
)
from .dataset import DatasetManifest
from .dataset_test_utils import TEST_DATASET_NAME, TEST_NAMESPACE, TestDataMaker, enriched_item
from .dataset_utils import lilac_span

SIMPLE_ITEMS: list[Item] = [{
  UUID_COLUMN: '1',
  'str': 'a',
  'int': 1,
  'bool': False,
  'float': 3.0
}, {
  UUID_COLUMN: '2',
  'str': 'b',
  'int': 2,
  'bool': True,
  'float': 2.0
}, {
  UUID_COLUMN: '3',
  'str': 'b',
  'int': 2,
  'bool': True,
  'float': 1.0
}]

EMBEDDINGS: list[tuple[str, list[float]]] = [('hello.', [1.0, 0.0, 0.0]),
                                             ('hello2.', [1.0, 1.0, 0.0]),
                                             ('hello world.', [1.0, 1.0, 1.0]),
                                             ('hello world2.', [2.0, 1.0, 1.0])]

STR_EMBEDDINGS: dict[str, list[float]] = {text: embedding for text, embedding in EMBEDDINGS}


class TestSplitter(TextSplitterSignal):
  """Split documents into sentence by splitting on period."""
  name = 'test_splitter'

  @override
  def compute(self, data: Iterable[RichData]) -> Iterable[Item]:
    for text in data:
      if not isinstance(text, str):
        raise ValueError(f'Expected text to be a string, got {type(text)} instead.')
      sentences = [f'{sentence.strip()}.' for sentence in text.split('.') if sentence]
      yield [
        lilac_span(text.index(sentence),
                   text.index(sentence) + len(sentence)) for sentence in sentences
      ]


class TestEmbedding(TextEmbeddingSignal):
  """A test embed function."""
  name = 'test_embedding'

  @override
  def compute(self, data: Iterable[RichData]) -> Iterable[Item]:
    """Call the embedding function."""
    yield from [np.array(STR_EMBEDDINGS[cast(str, example)]) for example in data]


class TestEmbeddingSumSignal(TextEmbeddingModelSignal):
  """Sums the embeddings to return a single floating point value."""
  name = 'test_embedding_sum'

  @override
  def fields(self) -> Field:
    return field('float32')

  @override
  def vector_compute(self, keys: Iterable[VectorKey], vector_store: VectorStore) -> Iterable[Item]:
    # The signal just sums the values of the embedding.
    embedding_sums = vector_store.get(keys).sum(axis=1)
    for embedding_sum in embedding_sums.tolist():
      yield embedding_sum


@pytest.fixture(scope='module', autouse=True)
def setup_teardown() -> Iterable[None]:
  # Setup.
  register_signal(TestSplitter)
  register_signal(TestEmbedding)
  register_signal(TestEmbeddingSumSignal)
  register_signal(EntitySignal)
  # Unit test runs.
  yield
  # Teardown.
  clear_signal_registry()


def test_manual_embedding_signal(make_test_data: TestDataMaker, mocker: MockerFixture) -> None:
  dataset = make_test_data([{
    UUID_COLUMN: '1',
    'text': 'hello.',
  }, {
    UUID_COLUMN: '2',
    'text': 'hello2.',
  }])

  embed_mock = mocker.spy(TestEmbedding, 'compute')

  embedding_signal = TestEmbedding()
  dataset.compute_signal(embedding_signal, 'text')
  embedding_sum_signal = TestEmbeddingSumSignal(embedding=TestEmbedding.name)
  dataset.compute_signal(embedding_sum_signal, 'text')

  # Make sure the embedding signal is not called twice.
  assert embed_mock.call_count == 1

  assert dataset.manifest() == DatasetManifest(
    namespace=TEST_NAMESPACE,
    dataset_name=TEST_DATASET_NAME,
    data_schema=schema({
      UUID_COLUMN: 'string',
      'text': field(
        {
          'test_embedding': signal_field(
            dtype='embedding',
            fields={
              'test_embedding_sum': signal_field(
                dtype='float32', signal=embedding_sum_signal.dict())
            },
            signal=embedding_signal.dict())
        },
        dtype='string'),
    }),
    num_items=2)

  result = dataset.select_rows()
  expected_result = [{
    UUID_COLUMN: '1',
    'text': enriched_item('hello.',
                          {'test_embedding': {
                            VALUE_KEY: None,
                            'test_embedding_sum': 1.0
                          }})
  }, {
    UUID_COLUMN: '2',
    'text': enriched_item('hello2.',
                          {'test_embedding': {
                            VALUE_KEY: None,
                            'test_embedding_sum': 2.0
                          }})
  }]
  assert list(result) == expected_result


def test_auto_embedding_signal(make_test_data: TestDataMaker, mocker: MockerFixture) -> None:
  dataset = make_test_data([{
    UUID_COLUMN: '1',
    'text': 'hello.',
  }, {
    UUID_COLUMN: '2',
    'text': 'hello2.',
  }])

  embed_mock = mocker.spy(TestEmbedding, 'compute')

  # The embedding is automatically computed from the TestEmbeddingSumSignal.
  embedding_sum_signal = TestEmbeddingSumSignal(embedding=TestEmbedding.name)
  dataset.compute_signal(embedding_sum_signal, 'text')

  # Make sure the embedding signal is not called twice.
  assert embed_mock.call_count == 1

  assert dataset.manifest() == DatasetManifest(
    namespace=TEST_NAMESPACE,
    dataset_name=TEST_DATASET_NAME,
    data_schema=schema({
      UUID_COLUMN: 'string',
      'text': field(
        {
          'test_embedding': signal_field(
            dtype='embedding',
            fields={
              'test_embedding_sum': signal_field(
                dtype='float32', signal=embedding_sum_signal.dict())
            },
            signal=cast(Signal, embedding_sum_signal._embedding_signal).dict())
        },
        dtype='string'),
    }),
    num_items=2)

  result = dataset.select_rows()
  expected_result = [{
    UUID_COLUMN: '1',
    'text': enriched_item('hello.',
                          {'test_embedding': {
                            VALUE_KEY: None,
                            'test_embedding_sum': 1.0
                          }})
  }, {
    UUID_COLUMN: '2',
    'text': enriched_item('hello2.',
                          {'test_embedding': {
                            VALUE_KEY: None,
                            'test_embedding_sum': 2.0
                          }})
  }]
  assert list(result) == expected_result


def test_manual_embedding_signal_splits(make_test_data: TestDataMaker,
                                        mocker: MockerFixture) -> None:
  dataset = make_test_data([{
    UUID_COLUMN: '1',
    'text': 'hello. hello2.',
  }, {
    UUID_COLUMN: '2',
    'text': 'hello world. hello world2.',
  }])

  split_mock = mocker.spy(TestSplitter, 'compute')
  embed_mock = mocker.spy(TestEmbedding, 'compute')

  split_signal = TestSplitter()
  dataset.compute_signal(split_signal, 'text')
  embedding_signal = TestEmbedding(split=TestSplitter.name)
  dataset.compute_signal(embedding_signal, 'text')
  embedding_sum_signal = TestEmbeddingSumSignal(
    split=TestSplitter.name, embedding=TestEmbedding.name)
  dataset.compute_signal(embedding_sum_signal, 'text')

  # Make sure the split and embedding signals are not called twice.
  assert split_mock.call_count == 1
  assert embed_mock.call_count == 1

  assert dataset.manifest() == DatasetManifest(
    namespace=TEST_NAMESPACE,
    dataset_name=TEST_DATASET_NAME,
    data_schema=schema({
      UUID_COLUMN: 'string',
      'text': field(
        {
          'test_splitter': signal_field(
            fields=[
              signal_field(
                dtype='string_span',
                fields={
                  'test_embedding': signal_field(
                    fields={
                      'test_embedding_sum': signal_field(
                        dtype='float32', signal=embedding_sum_signal.dict())
                    },
                    dtype='embedding',
                    signal=embedding_signal.dict())
                },
              )
            ],
            signal=split_signal.dict())
        },
        dtype='string'),
    }),
    num_items=2)

  result = dataset.select_rows(['text'])

  assert list(result) == [{
    UUID_COLUMN: '1',
    'text': enriched_item(
      'hello. hello2.', {
        'test_splitter': [
          lilac_span(0, 6, {
            'test_embedding': {
              VALUE_KEY: None,
              'test_embedding_sum': 1.0
            },
          }),
          lilac_span(7, 14, {
            'test_embedding': {
              VALUE_KEY: None,
              'test_embedding_sum': 2.0
            },
          }),
        ]
      })
  }, {
    UUID_COLUMN: '2',
    'text': enriched_item(
      'hello world. hello world2.', {
        'test_splitter': [
          lilac_span(0, 12, {
            'test_embedding': {
              VALUE_KEY: None,
              'test_embedding_sum': 3.0
            },
          }),
          lilac_span(13, 26, {
            'test_embedding': {
              VALUE_KEY: None,
              'test_embedding_sum': 4.0
            },
          })
        ]
      })
  }]


def test_auto_embedding_signal_splits(make_test_data: TestDataMaker, mocker: MockerFixture) -> None:
  dataset = make_test_data([{
    UUID_COLUMN: '1',
    'text': 'hello. hello2.',
  }, {
    UUID_COLUMN: '2',
    'text': 'hello world. hello world2.',
  }])

  split_mock = mocker.spy(TestSplitter, 'compute')
  embed_mock = mocker.spy(TestEmbedding, 'compute')

  embedding_sum_signal = TestEmbeddingSumSignal(
    split=TestSplitter.name, embedding=TestEmbedding.name)
  dataset.compute_signal(embedding_sum_signal, 'text')

  # Make sure the split and embedding signals are not called twice.
  assert split_mock.call_count == 1
  assert embed_mock.call_count == 1

  assert dataset.manifest() == DatasetManifest(
    namespace=TEST_NAMESPACE,
    dataset_name=TEST_DATASET_NAME,
    data_schema=schema({
      UUID_COLUMN: 'string',
      'text': field(
        {
          'test_splitter': signal_field(
            fields=[
              signal_field(
                dtype='string_span',
                fields={
                  'test_embedding': signal_field(
                    fields={
                      'test_embedding_sum': signal_field(
                        dtype='float32', signal=embedding_sum_signal.dict())
                    },
                    dtype='embedding',
                    signal=cast(Signal, embedding_sum_signal._embedding_signal).dict())
                },
              )
            ],
            signal=cast(Signal, embedding_sum_signal._split_signal).dict())
        },
        dtype='string'),
    }),
    num_items=2)

  result = dataset.select_rows(['text'])

  assert list(result) == [{
    UUID_COLUMN: '1',
    'text': enriched_item(
      'hello. hello2.', {
        'test_splitter': [
          lilac_span(0, 6, {
            'test_embedding': {
              VALUE_KEY: None,
              'test_embedding_sum': 1.0
            },
          }),
          lilac_span(7, 14, {
            'test_embedding': {
              VALUE_KEY: None,
              'test_embedding_sum': 2.0
            },
          }),
        ]
      })
  }, {
    UUID_COLUMN: '2',
    'text': enriched_item(
      'hello world. hello world2.', {
        'test_splitter': [
          lilac_span(0, 12, {
            'test_embedding': {
              VALUE_KEY: None,
              'test_embedding_sum': 3.0
            },
          }),
          lilac_span(13, 26, {
            'test_embedding': {
              VALUE_KEY: None,
              'test_embedding_sum': 4.0
            },
          })
        ]
      })
  }]


ENTITY_REGEX = r'[A-Za-z]+@[A-Za-z]+'


class EntitySignal(TextSignal):
  """Find special entities."""
  name = 'entity'

  @override
  def fields(self) -> Field:
    return field(['string_span'])

  @override
  def compute(self, data: Iterable[RichData]) -> Iterable[Optional[List[Item]]]:
    for text in data:
      if not isinstance(text, str):
        yield None
        continue
      yield [lilac_span(m.start(0), m.end(0)) for m in re.finditer(ENTITY_REGEX, text)]


def test_entity_on_split_signal(make_test_data: TestDataMaker) -> None:
  text = 'Hello nik@test. Here are some other entities like pii@gmail and all@lilac.'
  dataset = make_test_data([{UUID_COLUMN: '1', 'text': text}])
  entity = EntitySignal(split='test_splitter')
  dataset.compute_signal(entity, 'text')

  result = dataset.select_rows(['text'])
  assert list(result) == [{
    UUID_COLUMN: '1',
    'text': enriched_item(
      text, {
        'test_splitter': [
          lilac_span(0, 15, {'entity': [lilac_span(6, 14)]}),
          lilac_span(16, 74, {'entity': [
            lilac_span(50, 59),
            lilac_span(64, 73),
          ]}),
        ]
      })
  }]
