"""Tests for dataset.compute_signal()."""

from typing import Iterable, Optional, Union, cast

import numpy as np
import pytest
from typing_extensions import override

from ..concepts.concept import ExampleIn
from ..concepts.db_concept import ConceptUpdate, DiskConceptDB
from ..schema import (
  EMBEDDING_KEY,
  Field,
  Item,
  RichData,
  SignalInputType,
  field,
  lilac_embedding,
  lilac_span,
  schema,
)
from ..signal import (
  TextEmbeddingSignal,
  TextSignal,
  TextSplitterSignal,
  clear_signal_registry,
  register_signal,
)
from ..signals.concept_scorer import ConceptSignal
from .dataset import Column, DatasetManifest, GroupsSortBy, SortOrder
from .dataset_test_utils import TEST_DATASET_NAME, TEST_NAMESPACE, TestDataMaker, enriched_item

SIMPLE_ITEMS: list[Item] = [{
  'str': 'a',
  'int': 1,
  'bool': False,
  'float': 3.0
}, {
  'str': 'b',
  'int': 2,
  'bool': True,
  'float': 2.0
}, {
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
  def compute(self, data: Iterable[RichData]) -> Iterable[Optional[Item]]:
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
    return field(fields={'emails': ['string']})

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

  def compute(self, data: Iterable[RichData]) -> Iterable[Optional[Item]]:
    for text_content in data:
      yield f'{str(text_content)}_{self.param}'


class TestSignal(TextSignal):
  name = 'test_signal'

  @override
  def fields(self) -> Field:
    return field(fields={'len': 'int32', 'flen': 'float32'})

  @override
  def compute(self, data: Iterable[RichData]) -> Iterable[Optional[Item]]:
    return [{'len': len(text_content), 'flen': float(len(text_content))} for text_content in data]


class TestSplitSignal(TextSplitterSignal):
  """Split documents into sentence by splitting on period, generating entities."""
  name = 'test_split'

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


EMBEDDINGS: list[tuple[str, Union[list[float], list[list[float]]]]] = [
  ('hello.', [1.0, 0.0, 0.0]),
  # This embedding has an outer dimension of 1.
  ('hello2.', [[1.0, 1.0, 0.0]]),
  ('hello3.', [[0, 0, 1.]])
]

STR_EMBEDDINGS: dict[str, Union[list[float], list[list[float]]]] = {
  text: embedding for text, embedding in EMBEDDINGS
}


class TestEmbedding(TextEmbeddingSignal):
  """A test embed function."""
  name = 'test_embedding'

  @override
  def compute(self, data: Iterable[RichData]) -> Iterable[Item]:
    """Call the embedding function."""
    for example in data:
      example = cast(str, example)
      yield [lilac_embedding(0, len(example), np.array(STR_EMBEDDINGS[example]))]


class ComputedKeySignal(TextSignal):
  name = 'computed_key'

  @override
  def fields(self) -> Field:
    return field('int64')

  @override
  def compute(self, data: Iterable[RichData]) -> Iterable[Optional[Item]]:
    for text in data:
      yield 1

  def key(self, is_computed_signal: Optional[bool] = False) -> str:
    return f'key_{is_computed_signal}'


@pytest.fixture(scope='module', autouse=True)
def setup_teardown() -> Iterable[None]:
  # Setup.
  clear_signal_registry()
  register_signal(TestSparseSignal)
  register_signal(TestSparseRichSignal)
  register_signal(TestParamSignal)
  register_signal(TestSignal)
  register_signal(TestSplitSignal)
  register_signal(TestEmbedding)
  register_signal(ComputedKeySignal)
  register_signal(ConceptSignal)

  # Unit test runs.
  yield
  # Teardown.
  clear_signal_registry()


def test_signal_output_validation(make_test_data: TestDataMaker) -> None:
  signal = TestInvalidSignal()

  dataset = make_test_data([{
    'text': 'hello',
  }, {
    'text': 'hello world',
  }])

  with pytest.raises(
      ValueError, match='The signal generated 0 values but the input data had 2 values.'):
    dataset.compute_signal(signal, 'text')


def test_sparse_signal(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data([{
    'text': 'hello',
  }, {
    'text': 'hello world',
  }])

  dataset.compute_signal(TestSparseSignal(), 'text')

  result = dataset.select_rows(['text'], combine_columns=True)
  assert list(result) == [{
    'text': enriched_item('hello', {'test_sparse_signal': None})
  }, {
    'text': enriched_item('hello world', {'test_sparse_signal': 11})
  }]


def test_sparse_rich_signal(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data([{
    'text': 'hello',
  }, {
    'text': 'hello world',
  }])

  dataset.compute_signal(TestSparseRichSignal(), 'text')

  result = dataset.select_rows(['text'], combine_columns=True)
  assert list(result) == [{
    'text': enriched_item('hello', {'test_sparse_rich_signal': None})
  }, {
    'text': enriched_item(
      'hello world',
      {'test_sparse_rich_signal': {
        'emails': ['test1@hello.com', 'test2@hello.com']
      }})
  }]


def test_source_joined_with_signal(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data(SIMPLE_ITEMS)
  assert dataset.manifest() == DatasetManifest(
    namespace=TEST_NAMESPACE,
    dataset_name=TEST_DATASET_NAME,
    data_schema=schema({
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
      'str': field(
        'string',
        fields={
          'test_signal': field(
            signal=test_signal.dict(), fields={
              'len': 'int32',
              'flen': 'float32'
            }),
        }),
      'int': 'int32',
      'bool': 'boolean',
      'float': 'float32',
    }),
    num_items=3)

  result = dataset.select_rows(['str'], combine_columns=True)
  assert list(result) == [{
    'str': enriched_item('a', {'test_signal': {
      'len': 1,
      'flen': 1.0
    }}),
  }, {
    'str': enriched_item('b', {'test_signal': {
      'len': 1,
      'flen': 1.0
    }}),
  }, {
    'str': enriched_item('b', {'test_signal': {
      'len': 1,
      'flen': 1.0
    }}),
  }]

  # Select a specific signal leaf test_signal.flen with 'str'.
  result = dataset.select_rows(['str', ('str', 'test_signal', 'flen')])

  assert list(result) == [{
    'str': 'a',
    'str.test_signal.flen': 1.0
  }, {
    'str': 'b',
    'str.test_signal.flen': 1.0
  }, {
    'str': 'b',
    'str.test_signal.flen': 1.0
  }]

  # Select multiple signal leafs with aliasing.
  result = dataset.select_rows([
    'str',
    Column(('str', 'test_signal', 'flen'), alias='flen'),
    Column(('str', 'test_signal', 'len'), alias='len')
  ])

  assert list(result) == [{
    'str': 'a',
    'flen': 1.0,
    'len': 1
  }, {
    'str': 'b',
    'flen': 1.0,
    'len': 1
  }, {
    'str': 'b',
    'flen': 1.0,
    'len': 1
  }]


def test_parameterized_signal(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data([{'text': 'hello'}, {'text': 'everybody'}])
  test_signal_a = TestParamSignal(param='a')
  test_signal_b = TestParamSignal(param='b')
  dataset.compute_signal(test_signal_a, 'text')
  dataset.compute_signal(test_signal_b, 'text')

  assert dataset.manifest() == DatasetManifest(
    namespace=TEST_NAMESPACE,
    dataset_name=TEST_DATASET_NAME,
    data_schema=schema({
      'text': field(
        'string',
        fields={
          'param_signal(param=a)': field('string', test_signal_a.dict()),
          'param_signal(param=b)': field('string', test_signal_b.dict()),
        }),
    }),
    num_items=2)

  result = dataset.select_rows(['text'], combine_columns=True)
  assert list(result) == [{
    'text': enriched_item('hello', {
      'param_signal(param=a)': 'hello_a',
      'param_signal(param=b)': 'hello_b',
    })
  }, {
    'text': enriched_item('everybody', {
      'param_signal(param=a)': 'everybody_a',
      'param_signal(param=b)': 'everybody_b',
    })
  }]


def test_split_signal(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data([{
    'text': '[1, 1] first sentence. [1, 1] second sentence.',
  }, {
    'text': 'b2 [2, 1] first sentence. [2, 1] second sentence.',
  }])

  signal = TestSplitSignal()
  dataset.compute_signal(signal, 'text')

  assert dataset.manifest() == DatasetManifest(
    namespace=TEST_NAMESPACE,
    dataset_name=TEST_DATASET_NAME,
    data_schema=schema({
      'text': field(
        'string', fields={'test_split': field(signal=signal.dict(), fields=[field('string_span')])})
    }),
    num_items=2)

  result = dataset.select_rows(['text'], combine_columns=True)
  expected_result = [{
    'text': enriched_item('[1, 1] first sentence. [1, 1] second sentence.',
                          {'test_split': [lilac_span(0, 22), lilac_span(23, 46)]})
  }, {
    'text': enriched_item('b2 [2, 1] first sentence. [2, 1] second sentence.',
                          {'test_split': [
                            lilac_span(0, 25),
                            lilac_span(26, 49),
                          ]})
  }]
  assert list(result) == expected_result


def test_signal_on_repeated_field(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data([{
    'text': ['hello', 'everybody'],
  }, {
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
      'text': field(fields=[
        field(
          'string',
          fields={
            'test_signal': field(
              signal=test_signal.dict(), fields={
                'len': 'int32',
                'flen': 'float32'
              })
          })
      ])
    }),
    num_items=2)

  result = dataset.select_rows([('text', '*')], combine_columns=True)

  assert list(result) == [{
    'text': [
      enriched_item('hello', {'test_signal': {
        'len': 5,
        'flen': 5.0
      }}),
      enriched_item('everybody', {'test_signal': {
        'len': 9,
        'flen': 9.0
      }})
    ]
  }, {
    'text': [
      enriched_item('hello2', {'test_signal': {
        'len': 6,
        'flen': 6.0
      }}),
      enriched_item('everybody2', {'test_signal': {
        'len': 10,
        'flen': 10.0
      }})
    ]
  }]


def test_text_splitter(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data([{
    'text': '[1, 1] first sentence. [1, 1] second sentence.',
  }, {
    'text': 'b2 [2, 1] first sentence. [2, 1] second sentence.',
  }])

  dataset.compute_signal(TestSplitSignal(), 'text')

  result = dataset.select_rows(['text'], combine_columns=True)
  expected_result = [{
    'text': enriched_item('[1, 1] first sentence. [1, 1] second sentence.',
                          {'test_split': [
                            lilac_span(0, 22),
                            lilac_span(23, 46),
                          ]}),
  }, {
    'text': enriched_item('b2 [2, 1] first sentence. [2, 1] second sentence.',
                          {'test_split': [
                            lilac_span(0, 25),
                            lilac_span(26, 49),
                          ]}),
  }]
  assert list(result) == expected_result


def test_embedding_signal(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data([{'text': 'hello.'}, {'text': 'hello2.'}])

  embedding_signal = TestEmbedding()
  dataset.compute_signal(embedding_signal, 'text')

  assert dataset.manifest() == DatasetManifest(
    namespace=TEST_NAMESPACE,
    dataset_name=TEST_DATASET_NAME,
    data_schema=schema({
      'text': field(
        'string',
        fields={
          'test_embedding': field(
            signal=embedding_signal.dict(),
            fields=[field('string_span', fields={EMBEDDING_KEY: 'embedding'})])
        }),
    }),
    num_items=2)

  result = dataset.select_rows(combine_columns=True)
  expected_result = [{'text': 'hello.'}, {'text': 'hello2.'}]
  assert list(result) == expected_result


def test_is_computed_signal_key(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data([{'text': 'hello.'}, {'text': 'hello2.'}])

  signal = ComputedKeySignal()
  dataset.compute_signal(signal, 'text')

  assert dataset.manifest() == DatasetManifest(
    namespace=TEST_NAMESPACE,
    dataset_name=TEST_DATASET_NAME,
    data_schema=schema({
      'text': field('string', fields={'key_True': field('int64', signal=signal.dict())}),
    }),
    num_items=2)

  result = dataset.select_rows(combine_columns=True)

  expected_result = [{
    'text': enriched_item('hello.', {'key_True': 1})
  }, {
    'text': enriched_item('hello2.', {'key_True': 1})
  }]
  assert list(result) == expected_result


def test_concept_signal_with_select_groups(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data([{
    'text': 'hello.',
  }, {
    'text': 'hello2.',
  }, {
    'text': 'hello3.',
  }])

  embedding_signal = TestEmbedding()
  dataset.compute_signal(embedding_signal, 'text')

  concept_db = DiskConceptDB()
  concept_db.create(namespace='test_namespace', name='test_concept', type=SignalInputType.TEXT)
  concept_db.edit(
    'test_namespace', 'test_concept',
    ConceptUpdate(insert=[
      ExampleIn(label=False, text='hello.'),
      ExampleIn(label=True, text='hello2.'),
      ExampleIn(label=False, text='hello3.')
    ]))

  dataset.compute_concept(
    namespace='test_namespace',
    concept_name='test_concept',
    embedding='test_embedding',
    path='text')

  concept_key = 'test_namespace/test_concept/test_embedding/v1'
  result = dataset.select_groups(f'text.{concept_key}.*.score')
  assert result.counts == [('Not in concept', 2), ('In concept', 1)]

  result = dataset.select_groups(
    f'text.{concept_key}.*.score', sort_by=GroupsSortBy.COUNT, sort_order=SortOrder.ASC)
  assert result.counts == [('In concept', 1), ('Not in concept', 2)]
