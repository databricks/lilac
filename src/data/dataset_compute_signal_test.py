"""Tests for dataset.compute_signal()."""

from typing import Iterable, Optional, Union, cast

import numpy as np
import pytest
from typing_extensions import override

from ..schema import (
  SIGNAL_METADATA_KEY,
  UUID_COLUMN,
  VALUE_KEY,
  DataType,
  Field,
  Item,
  ItemValue,
  RichData,
  SignalOut,
  field,
  schema,
  signal_field,
)
from ..signals.signal import (
  TextEmbeddingSignal,
  TextSignal,
  TextSplitterSignal,
  clear_signal_registry,
  register_signal,
)
from .dataset import Column, DatasetManifest, val
from .dataset_test_utils import TEST_DATASET_NAME, TEST_NAMESPACE, TestDataMaker
from .dataset_utils import lilac_item, lilac_items, lilac_span, signal_item

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


class TestInvalidSignal(TextSignal):
  name = 'test_invalid_signal'

  @override
  def fields(self) -> Field:
    return field('int32')

  @override
  def compute(self, data: Iterable[RichData]) -> Iterable[Optional[Item]]:
    # Return an invalid output that doesn't match the input length.
    return []


class TestSparseSignal(TextSignal):
  name = 'test_sparse_signal'

  @override
  def fields(self) -> Field:
    return field('int32')

  @override
  def compute(self, data: Iterable[RichData]) -> Iterable[Optional[ItemValue]]:
    for text in data:
      if text == 'hello':
        # Skip this input.
        yield None
      else:
        yield len(text)


class TestSparseRichSignal(TextSignal):
  """Find personally identifiable information (emails, phone numbers, etc)."""
  name = 'test_sparse_rich_signal'

  @override
  def fields(self) -> Field:
    return field({'emails': ['string']})

  @override
  def compute(self, data: Iterable[RichData]) -> Iterable[Optional[Item]]:
    for text in data:
      if text == 'hello':
        # Skip this input.
        yield None
      else:
        yield {'emails': ['test1@hello.com', 'test2@hello.com']}


class TestParamSignal(TextSignal):
  name = 'param_signal'
  param: str

  def fields(self) -> Field:
    return field('string')

  def compute(self, data: Iterable[RichData]) -> Iterable[Optional[SignalOut]]:
    for text_content in data:
      yield f'{str(text_content)}_{self.param}'


class TestSignal(TextSignal):
  name = 'test_signal'

  @override
  def fields(self) -> Field:
    return field({'len': 'int32', 'flen': 'float32'})

  @override
  def compute(self, data: Iterable[RichData]) -> Iterable[Optional[Item]]:
    return [{'len': len(text_content), 'flen': float(len(text_content))} for text_content in data]


class TestSplitSignal(TextSplitterSignal):
  """Split documents into sentence by splitting on period, generating entities.

  Also produces the length as a feature.
  """
  name = 'test_split_len'

  @override
  def fields(self) -> Field:
    return field([
      Field(
        dtype=DataType.STRING_SPAN, fields={SIGNAL_METADATA_KEY: field({'len': field('int32')})})
    ])

  @override
  def compute(self, data: Iterable[RichData]) -> Iterable[ItemValue]:
    for text in data:
      if not isinstance(text, str):
        raise ValueError(f'Expected text to be a string, got {type(text)} instead.')
      sentences = [f'{sentence.strip()}.' for sentence in text.split('.') if sentence]
      yield [
        signal_item(
          lilac_span(text.index(sentence),
                     text.index(sentence) + len(sentence)), {'len': len(sentence)})
        for sentence in sentences
      ]


EMBEDDINGS: list[tuple[str, Union[list[float], list[list[float]]]]] = [
  ('hello.', [1.0, 0.0, 0.0]),
  # This embedding has an outer dimension of 1.
  ('hello2.', [[1.0, 1.0, 0.0]])
]

STR_EMBEDDINGS: dict[str, Union[list[float], list[list[float]]]] = {
  text: embedding for text, embedding in EMBEDDINGS
}


class TestEmbedding(TextEmbeddingSignal):
  """A test embed function."""
  name = 'test_embedding'

  @override
  def compute(self, data: Iterable[RichData]) -> Iterable[SignalOut]:
    """Call the embedding function."""
    yield from [np.array(STR_EMBEDDINGS[cast(str, example)]) for example in data]


@pytest.fixture(scope='module', autouse=True)
def setup_teardown() -> Iterable[None]:
  # Setup.
  register_signal(TestSparseSignal)
  register_signal(TestSparseRichSignal)
  register_signal(TestParamSignal)
  register_signal(TestSignal)
  register_signal(TestSplitSignal)
  register_signal(TestEmbedding)
  # Unit test runs.
  yield
  # Teardown.
  clear_signal_registry()


def test_signal_output_validation(make_test_data: TestDataMaker) -> None:
  signal = TestInvalidSignal()

  dataset = make_test_data([{
    UUID_COLUMN: '1',
    'text': 'hello',
  }, {
    UUID_COLUMN: '2',
    'text': 'hello world',
  }])

  with pytest.raises(
      ValueError, match='The signal generated 0 values but the input data had 2 values.'):
    dataset.compute_signal(signal, 'text')


def test_sparse_signal(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data([{
    UUID_COLUMN: '1',
    'text': 'hello',
  }, {
    UUID_COLUMN: '2',
    'text': 'hello world',
  }])

  dataset.compute_signal(TestSparseSignal(), 'text')

  result = dataset.select_rows(['text'])
  assert list(result) == lilac_items([{
    UUID_COLUMN: '1',
    'text': lilac_item('hello', {'test_sparse_signal': None})
  }, {
    UUID_COLUMN: '2',
    'text': lilac_item('hello world', {'test_sparse_signal': 11})
  }])


def test_sparse_rich_signal(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data([{
    UUID_COLUMN: '1',
    'text': 'hello',
  }, {
    UUID_COLUMN: '2',
    'text': 'hello world',
  }])

  dataset.compute_signal(TestSparseRichSignal(), 'text')

  result = dataset.select_rows(['text'])
  assert list(result) == lilac_items([{
    UUID_COLUMN: '1',
    'text': lilac_item('hello', {'test_sparse_rich_signal': None})
  }, {
    UUID_COLUMN: '2',
    'text': lilac_item(
      'hello world',
      {'test_sparse_rich_signal': {
        'emails': ['test1@hello.com', 'test2@hello.com']
      }})
  }])


def test_source_joined_with_signal_column(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data(SIMPLE_ITEMS)
  assert dataset.manifest() == DatasetManifest(
    namespace=TEST_NAMESPACE,
    dataset_name=TEST_DATASET_NAME,
    data_schema=schema({
      UUID_COLUMN: 'string',
      'str': 'string',
      'int': 'int32',
      'bool': 'boolean',
      'float': 'float32',
    }),
    num_items=3)

  test_signal = TestSignal()
  dataset.compute_signal(test_signal, 'str')

  # Check the enriched dataset manifest has 'text' enriched.
  assert dataset.manifest() == DatasetManifest(
    namespace=TEST_NAMESPACE,
    dataset_name=TEST_DATASET_NAME,
    data_schema=schema({
      UUID_COLUMN: 'string',
      'str': field(
        {
          'test_signal': signal_field(
            fields={
              'len': 'int32',
              'flen': 'float32'
            }, signal=test_signal.dict()),
        },
        dtype='string'),
      'int': 'int32',
      'bool': 'boolean',
      'float': 'float32',
    }),
    num_items=3)

  result = dataset.select_rows(['str'])
  assert list(result) == lilac_items([{
    UUID_COLUMN: '1',
    'str': lilac_item('a', {'test_signal': {
      'len': 1,
      'flen': 1.0
    }}),
  }, {
    UUID_COLUMN: '2',
    'str': lilac_item('b', {'test_signal': {
      'len': 1,
      'flen': 1.0
    }}),
  }, {
    UUID_COLUMN: '3',
    'str': lilac_item('b', {'test_signal': {
      'len': 1,
      'flen': 1.0
    }}),
  }])

  # Select a specific signal leaf test_signal.flen with val('str').
  result = dataset.select_rows([val('str'), ('str', 'test_signal', 'flen')])

  assert list(result) == [{
    UUID_COLUMN: '1',
    f'str.{VALUE_KEY}': 'a',
    'str.test_signal.flen': lilac_item(1.0)
  }, {
    UUID_COLUMN: '2',
    f'str.{VALUE_KEY}': 'b',
    'str.test_signal.flen': lilac_item(1.0)
  }, {
    UUID_COLUMN: '3',
    f'str.{VALUE_KEY}': 'b',
    'str.test_signal.flen': lilac_item(1.0)
  }]

  # Select a specific signal leaf test_signal.flen and the whole 'str' subtree.
  result = dataset.select_rows(['str', ('str', 'test_signal', 'flen')])

  assert list(result) == [{
    UUID_COLUMN: '1',
    'str': lilac_item('a', {'test_signal': {
      'len': 1,
      'flen': 1.0
    }}),
    'str.test_signal.flen': lilac_item(1.0)
  }, {
    UUID_COLUMN: '2',
    'str': lilac_item('b', {'test_signal': {
      'len': 1,
      'flen': 1.0
    }}),
    'str.test_signal.flen': lilac_item(1.0)
  }, {
    UUID_COLUMN: '3',
    'str': lilac_item('b', {'test_signal': {
      'len': 1,
      'flen': 1.0
    }}),
    'str.test_signal.flen': lilac_item(1.0)
  }]

  # Select multiple signal leafs with aliasing.
  result = dataset.select_rows([
    val('str'),
    Column(('str', 'test_signal', 'flen'), alias='flen'),
    Column(('str', 'test_signal', 'len'), alias='len')
  ])

  assert list(result) == [{
    UUID_COLUMN: '1',
    f'str.{VALUE_KEY}': 'a',
    'flen': lilac_item(1.0),
    'len': lilac_item(1)
  }, {
    UUID_COLUMN: '2',
    f'str.{VALUE_KEY}': 'b',
    'flen': lilac_item(1.0),
    'len': lilac_item(1)
  }, {
    UUID_COLUMN: '3',
    f'str.{VALUE_KEY}': 'b',
    'flen': lilac_item(1.0),
    'len': lilac_item(1)
  }]


def test_parameterized_signal(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data([{
    UUID_COLUMN: '1',
    'text': 'hello'
  }, {
    UUID_COLUMN: '2',
    'text': 'everybody'
  }])
  test_signal_a = TestParamSignal(param='a')
  test_signal_b = TestParamSignal(param='b')
  dataset.compute_signal(test_signal_a, 'text')
  dataset.compute_signal(test_signal_b, 'text')

  assert dataset.manifest() == DatasetManifest(
    namespace=TEST_NAMESPACE,
    dataset_name=TEST_DATASET_NAME,
    data_schema=schema({
      UUID_COLUMN: 'string',
      'text': field(
        {
          'param_signal(param=a)': signal_field(dtype='string', signal=test_signal_a.dict()),
          'param_signal(param=b)': signal_field(dtype='string', signal=test_signal_b.dict()),
        },
        dtype='string'),
    }),
    num_items=2)

  result = dataset.select_rows(['text'])
  assert list(result) == lilac_items([{
    UUID_COLUMN: '1',
    'text': lilac_item('hello', {
      'param_signal(param=a)': 'hello_a',
      'param_signal(param=b)': 'hello_b',
    })
  }, {
    UUID_COLUMN: '2',
    'text': lilac_item('everybody', {
      'param_signal(param=a)': 'everybody_a',
      'param_signal(param=b)': 'everybody_b',
    })
  }])


def test_split_signal(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data([{
    UUID_COLUMN: '1',
    'text': '[1, 1] first sentence. [1, 1] second sentence.',
  }, {
    UUID_COLUMN: '2',
    'text': 'b2 [2, 1] first sentence. [2, 1] second sentence.',
  }])

  signal = TestSplitSignal()
  dataset.compute_signal(signal, 'text')

  assert dataset.manifest() == DatasetManifest(
    namespace=TEST_NAMESPACE,
    dataset_name=TEST_DATASET_NAME,
    data_schema=schema({
      UUID_COLUMN: 'string',
      'text': field(
        {
          'test_split_len': signal_field(
            fields=[signal_field(dtype='string_span', metadata={'len': 'int32'})],
            signal=signal.dict())
        },
        dtype='string')
    }),
    num_items=2)

  result = dataset.select_rows(['text'])
  expected_result = [{
    UUID_COLUMN: '1',
    'text': lilac_item(
      '[1, 1] first sentence. [1, 1] second sentence.', {
        'test_split_len': [
          signal_item(lilac_span(0, 22), {'len': 22}),
          signal_item(lilac_span(23, 46), {'len': 23}),
        ]
      })
  }, {
    UUID_COLUMN: '2',
    'text': lilac_item(
      'b2 [2, 1] first sentence. [2, 1] second sentence.', {
        'test_split_len': [
          signal_item(lilac_span(0, 25), {'len': 25}),
          signal_item(lilac_span(26, 49), {'len': 23}),
        ]
      })
  }]
  assert list(result) == expected_result


def test_signal_on_repeated_field(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data([{
    UUID_COLUMN: '1',
    'text': ['hello', 'everybody'],
  }, {
    UUID_COLUMN: '2',
    'text': ['hello2', 'everybody2'],
  }])
  test_signal = TestSignal()
  # Run the signal on the repeated field.
  dataset.compute_signal(test_signal, ('text', '*'))

  # Check the enriched dataset manifest has 'text' enriched.
  assert dataset.manifest() == DatasetManifest(
    namespace=TEST_NAMESPACE,
    dataset_name=TEST_DATASET_NAME,
    data_schema=schema({
      UUID_COLUMN: 'string',
      'text': field([
        field(
          {
            'test_signal': signal_field(
              fields={
                'len': 'int32',
                'flen': 'float32'
              }, signal=test_signal.dict())
          },
          dtype='string')
      ])
    }),
    num_items=2)

  result = dataset.select_rows([('text', '*')])

  assert list(result) == [{
    UUID_COLUMN: '1',
    'text.*': [
      lilac_item('hello', {'test_signal': {
        'len': 5,
        'flen': 5.0
      }}),
      lilac_item('everybody', {'test_signal': {
        'len': 9,
        'flen': 9.0
      }})
    ]
  }, {
    UUID_COLUMN: '2',
    'text.*': [
      lilac_item('hello2', {'test_signal': {
        'len': 6,
        'flen': 6.0
      }}),
      lilac_item('everybody2', {'test_signal': {
        'len': 10,
        'flen': 10.0
      }})
    ]
  }]


def test_text_splitter(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data([{
    UUID_COLUMN: '1',
    'text': '[1, 1] first sentence. [1, 1] second sentence.',
  }, {
    UUID_COLUMN: '2',
    'text': 'b2 [2, 1] first sentence. [2, 1] second sentence.',
  }])

  dataset.compute_signal(TestSplitSignal(), 'text')

  result = dataset.select_rows(['text'])
  expected_result = [{
    UUID_COLUMN: '1',
    'text': lilac_item(
      '[1, 1] first sentence. [1, 1] second sentence.', {
        'test_split_len': [
          signal_item(lilac_span(0, 22), {'len': 22}),
          signal_item(lilac_span(23, 46), {'len': 23}),
        ]
      }),
  }, {
    UUID_COLUMN: '2',
    'text': lilac_item(
      'b2 [2, 1] first sentence. [2, 1] second sentence.', {
        'test_split_len': [
          signal_item(lilac_span(0, 25), {'len': 25}),
          signal_item(lilac_span(26, 49), {'len': 23}),
        ]
      }),
  }]
  assert list(result) == expected_result


def test_embedding_signal(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data([{
    UUID_COLUMN: '1',
    'text': 'hello.',
  }, {
    UUID_COLUMN: '2',
    'text': 'hello2.',
  }])

  embedding_signal = TestEmbedding(embedding=TestEmbedding.name)
  dataset.compute_signal(embedding_signal, 'text')

  assert dataset.manifest() == DatasetManifest(
    namespace=TEST_NAMESPACE,
    dataset_name=TEST_DATASET_NAME,
    data_schema=schema({
      UUID_COLUMN: 'string',
      'text': field(
        {'test_embedding': signal_field(dtype='embedding', signal=embedding_signal.dict())},
        dtype='string'),
    }),
    num_items=2)

  result = dataset.select_rows()

  # Embeddings are replaced with "None".
  expected_result = lilac_items([{
    UUID_COLUMN: '1',
    'text': lilac_item('hello.', {'test_embedding': lilac_item(None, allow_none_value=True)})
  }, {
    UUID_COLUMN: '2',
    'text': lilac_item('hello2.', {'test_embedding': lilac_item(None, allow_none_value=True)})
  }])
  assert list(result) == expected_result
