"""Tests for `db.select_rows_schema()`."""

from typing import Iterable, Optional, cast

import numpy as np
import pytest
from typing_extensions import override

from ..embeddings.vector_store import VectorStore
from ..schema import (
  UUID_COLUMN,
  Field,
  Item,
  ItemValue,
  RichData,
  SignalOut,
  VectorKey,
  field,
  schema,
  signal_field,
)
from ..signals.signal import (
  TextEmbeddingModelSignal,
  TextEmbeddingSignal,
  TextSignal,
  TextSplitterSignal,
  clear_signal_registry,
  register_signal,
)
from .dataset import Column, SelectRowsSchemaResult
from .dataset_test_utils import TestDataMaker
from .dataset_utils import lilac_span, signal_item

TEST_DATA: list[Item] = [{
  UUID_COLUMN: '1',
  'erased': False,
  'people': [{
    'name': 'A',
    'zipcode': 0,
    'locations': [{
      'city': 'city1',
      'state': 'state1'
    }, {
      'city': 'city2',
      'state': 'state2'
    }]
  }]
}, {
  UUID_COLUMN: '2',
  'erased': True,
  'people': [{
    'name': 'B',
    'zipcode': 1,
    'locations': [{
      'city': 'city3',
      'state': 'state3'
    }, {
      'city': 'city4'
    }, {
      'city': 'city5'
    }]
  }, {
    'name': 'C',
    'zipcode': 2,
    'locations': [{
      'city': 'city1',
      'state': 'state1'
    }]
  }]
}]


class TestSplitter(TextSplitterSignal):
  """Split documents into sentence by splitting on period."""
  name = 'test_splitter'

  @override
  def compute(self, data: Iterable[RichData]) -> Iterable[ItemValue]:
    for text in data:
      if not isinstance(text, str):
        raise ValueError(f'Expected text to be a string, got {type(text)} instead.')
      sentences = [f'{sentence.strip()}.' for sentence in text.split('.') if sentence]
      yield [
        signal_item(lilac_span(text.index(sentence),
                               text.index(sentence) + len(sentence))) for sentence in sentences
      ]


EMBEDDINGS: list[tuple[str, list[float]]] = [('hello.', [1.0, 0.0, 0.0]),
                                             ('hello2.', [1.0, 1.0, 0.0]),
                                             ('hello world.', [1.0, 1.0, 1.0]),
                                             ('hello world2.', [2.0, 1.0, 1.0])]

STR_EMBEDDINGS: dict[str, list[float]] = {text: embedding for text, embedding in EMBEDDINGS}


class TestEmbedding(TextEmbeddingSignal):
  """A test embed function."""
  name = 'test_embedding'

  @override
  def compute(self, data: Iterable[RichData]) -> Iterable[SignalOut]:
    """Call the embedding function."""
    embeddings = [np.array(STR_EMBEDDINGS[cast(str, example)]) for example in data]
    yield from embeddings


class TestEmbeddingSumSignal(TextEmbeddingModelSignal):
  """Sums the embeddings to return a single floating point value."""
  name = 'test_embedding_sum'

  @override
  def fields(self) -> Field:
    return field('float32')

  @override
  def vector_compute(self, keys: Iterable[VectorKey],
                     vector_store: VectorStore) -> Iterable[SignalOut]:
    # The signal just sums the values of the embedding.
    embedding_sums = vector_store.get(keys).sum(axis=1)
    for embedding_sum in embedding_sums.tolist():
      yield embedding_sum


@pytest.fixture(scope='module', autouse=True)
def setup_teardown() -> Iterable[None]:
  # Setup.
  register_signal(LengthSignal)
  register_signal(AddSpaceSignal)
  register_signal(TestSplitter)
  register_signal(TestEmbedding)
  register_signal(TestEmbeddingSumSignal)

  # Unit test runs.
  yield

  # Teardown.
  clear_signal_registry()


class LengthSignal(TextSignal):
  name = 'length_signal'

  def fields(self) -> Field:
    return field('int32')

  def compute(self, data: Iterable[RichData]) -> Iterable[Optional[SignalOut]]:
    for text_content in data:
      yield len(text_content)


class AddSpaceSignal(TextSignal):
  name = 'add_space_signal'

  def fields(self) -> Field:
    return field('string')

  def compute(self, data: Iterable[RichData]) -> Iterable[Optional[SignalOut]]:
    for text_content in data:
      yield cast(str, text_content) + ' '


def test_simple_schema(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data(TEST_DATA)
  result = dataset.select_rows_schema(combine_columns=True)
  assert result == SelectRowsSchemaResult(
    data_schema=schema({
      UUID_COLUMN: 'string',
      'erased': 'boolean',
      'people': [{
        'name': 'string',
        'zipcode': 'int32',
        'locations': [{
          'city': 'string',
          'state': 'string'
        }]
      }]
    }))


def test_subselection_with_combine_cols(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data(TEST_DATA)

  result = dataset.select_rows_schema([('people', '*', 'zipcode'),
                                       ('people', '*', 'locations', '*', 'city')],
                                      combine_columns=True)
  assert result == SelectRowsSchemaResult(
    data_schema=schema({
      UUID_COLUMN: 'string',
      'people': [{
        'zipcode': 'int32',
        'locations': [{
          'city': 'string'
        }]
      }]
    }))

  result = dataset.select_rows_schema([('people', '*', 'name'), ('people', '*', 'locations')],
                                      combine_columns=True)
  assert result == SelectRowsSchemaResult(
    data_schema=schema({
      UUID_COLUMN: 'string',
      'people': [{
        'name': 'string',
        'locations': [{
          'city': 'string',
          'state': 'string'
        }]
      }]
    }))

  result = dataset.select_rows_schema([('people', '*')], combine_columns=True)
  assert result == SelectRowsSchemaResult(
    data_schema=schema({
      UUID_COLUMN: 'string',
      'people': [{
        'name': 'string',
        'zipcode': 'int32',
        'locations': [{
          'city': 'string',
          'state': 'string'
        }]
      }]
    }))


def test_udf_with_combine_cols(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data(TEST_DATA)

  length_signal = LengthSignal()
  result = dataset.select_rows_schema([('people', '*', 'locations', '*', 'city'),
                                       Column(('people', '*', 'name'), signal_udf=length_signal)],
                                      combine_columns=True)
  assert result == SelectRowsSchemaResult(
    data_schema=schema({
      UUID_COLUMN: 'string',
      'people': [{
        'name': {
          'length_signal': signal_field(dtype='int32', signal=length_signal.dict())
        },
        'locations': [{
          'city': 'string'
        }]
      }],
    }))


def test_embedding_udf_with_combine_cols(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data(TEST_DATA)

  add_space_signal = AddSpaceSignal()
  dataset.compute_signal(add_space_signal, ('people', '*', 'name'))
  result = dataset.select_rows_schema(
    [('people', '*', 'name'),
     Column(('people', '*', 'name', 'add_space_signal'), signal_udf=add_space_signal)],
    combine_columns=True)
  assert result == SelectRowsSchemaResult(
    data_schema=schema({
      UUID_COLUMN: 'string',
      'people': [{
        'name': field(
          {
            'add_space_signal': signal_field(
              fields={
                'add_space_signal': signal_field(dtype='string', signal=add_space_signal.dict()),
              },
              dtype='string',
              signal=add_space_signal.dict())
          },
          dtype='string')
      }],
    }))


def test_udf_chained_with_combine_cols(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data([{
    UUID_COLUMN: '1',
    'text': 'hello. hello2.',
  }, {
    UUID_COLUMN: '2',
    'text': 'hello world. hello world2.',
  }])

  test_splitter = TestSplitter()
  dataset.compute_signal(test_splitter, ('text'))
  add_space_signal = AddSpaceSignal(split='test_splitter')
  result = dataset.select_rows_schema(
    [('text'), Column(('text'), signal_udf=add_space_signal)], combine_columns=True)

  assert result == SelectRowsSchemaResult(
    data_schema=schema({
      UUID_COLUMN: 'string',
      'text': field(
        {
          'test_splitter': signal_field(
            fields=[
              signal_field(
                dtype='string_span',
                fields={
                  'add_space_signal': signal_field(dtype='string', signal=add_space_signal.dict())
                })
            ],
            signal=test_splitter.dict())
        },
        dtype='string')
    }))


def test_udf_embedding_chained_with_combine_cols(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data([{
    UUID_COLUMN: '1',
    'text': 'hello. hello2.',
  }, {
    UUID_COLUMN: '2',
    'text': 'hello world. hello world2.',
  }])

  test_splitter = TestSplitter()
  dataset.compute_signal(test_splitter, 'text')
  test_embedding = TestEmbedding(split='test_splitter')
  dataset.compute_signal(test_embedding, 'text')

  embedding_sum_signal = TestEmbeddingSumSignal(split='test_splitter', embedding='test_embedding')
  result = dataset.select_rows_schema(
    [('text'), Column(('text'), signal_udf=embedding_sum_signal)], combine_columns=True)

  expected_schema = schema({
    UUID_COLUMN: 'string',
    'text': field(
      {
        'test_splitter': signal_field(
          fields=[
            signal_field(
              dtype='string_span',
              fields={
                'test_embedding': signal_field(
                  dtype='embedding',
                  fields={
                    'test_embedding_sum': signal_field(
                      dtype='float32', signal=embedding_sum_signal.dict())
                  },
                  signal=test_embedding.dict()),
              })
          ],
          signal=test_splitter.dict())
      },
      dtype='string')
  })
  assert result == SelectRowsSchemaResult(data_schema=expected_schema, alias_udf_paths={})

  # Alias the udf.
  result = dataset.select_rows_schema(
    [('text'), Column(('text'), signal_udf=embedding_sum_signal, alias='udf1')],
    combine_columns=True)
  assert result == SelectRowsSchemaResult(
    data_schema=expected_schema,
    alias_udf_paths={
      'udf1': ('text', 'test_splitter', '*', 'test_embedding', 'test_embedding_sum')
    })
