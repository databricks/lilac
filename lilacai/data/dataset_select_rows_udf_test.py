"""Tests for dataset.select_rows(udf_col)."""

from typing import Iterable, Optional, cast

import numpy as np
import pytest
from typing_extensions import override

from ..embeddings.vector_store import VectorStore
from ..schema import UUID_COLUMN, Field, Item, RichData, VectorKey, field
from ..signals.signal import (
  TextEmbeddingModelSignal,
  TextEmbeddingSignal,
  TextSignal,
  TextSplitterSignal,
  clear_signal_registry,
  register_signal,
)
from .dataset import BinaryFilterTuple, BinaryOp, Column
from .dataset_test_utils import TestDataMaker, enriched_item
from .dataset_utils import lilac_embedding, lilac_span

EMBEDDINGS: list[tuple[str, list[float]]] = [('hello.', [1.0, 0.0, 0.0]),
                                             ('hello2.', [1.0, 1.0, 0.0]),
                                             ('hello world.', [1.0, 1.0, 1.0]),
                                             ('hello world2.', [2.0, 1.0, 1.0])]

STR_EMBEDDINGS: dict[str, list[float]] = {text: embedding for text, embedding in EMBEDDINGS}


class TestEmbedding(TextEmbeddingSignal):
  """A test embed function."""
  name = 'test_embedding'

  @override
  def compute(self, data: Iterable[RichData]) -> Iterable[Item]:
    """Call the embedding function."""
    for example in data:
      yield [lilac_embedding(0, len(example), np.array(STR_EMBEDDINGS[cast(str, example)]))]


class LengthSignal(TextSignal):
  name = 'length_signal'

  _call_count: int = 0

  def fields(self) -> Field:
    return field('int32')

  def compute(self, data: Iterable[RichData]) -> Iterable[Optional[Item]]:
    for text_content in data:
      self._call_count += 1
      yield len(text_content)


class TestSignal(TextSignal):
  name = 'test_signal'

  @override
  def fields(self) -> Field:
    return field(fields={'len': 'int32', 'flen': 'float32'})

  @override
  def compute(self, data: Iterable[RichData]) -> Iterable[Optional[Item]]:
    return [{'len': len(text_content), 'flen': float(len(text_content))} for text_content in data]


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
  register_signal(LengthSignal)
  register_signal(TestSplitter)
  register_signal(TestEmbedding)
  register_signal(TestSignal)
  register_signal(TestEmbeddingSumSignal)
  register_signal(ComputedKeySignal)

  # Unit test runs.
  yield
  # Teardown.
  clear_signal_registry()


def test_udf(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data([{
    UUID_COLUMN: '1',
    'text': 'hello'
  }, {
    UUID_COLUMN: '2',
    'text': 'everybody'
  }])

  signal_col = Column('text', signal_udf=TestSignal())
  result = dataset.select_rows(['text', signal_col])

  assert list(result) == [{
    UUID_COLUMN: '1',
    'text': 'hello',
    'test_signal(text)': {
      'len': 5,
      'flen': 5.0
    }
  }, {
    UUID_COLUMN: '2',
    'text': 'everybody',
    'test_signal(text)': {
      'len': 9,
      'flen': 9.0
    }
  }]


def test_udf_with_filters(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data([{
    UUID_COLUMN: '1',
    'text': 'hello'
  }, {
    UUID_COLUMN: '2',
    'text': 'everybody'
  }])

  signal_col = Column('text', signal_udf=TestSignal())
  # Filter by source feature.
  filters: list[BinaryFilterTuple] = [('text', BinaryOp.EQUALS, 'everybody')]
  result = dataset.select_rows(['text', signal_col], filters=filters)
  assert list(result) == [{
    UUID_COLUMN: '2',
    'text': 'everybody',
    'test_signal(text)': {
      'len': 9,
      'flen': 9.0
    }
  }]


def test_udf_with_uuid_filter(make_test_data: TestDataMaker) -> None:

  dataset = make_test_data([{
    UUID_COLUMN: '1',
    'text': 'hello'
  }, {
    UUID_COLUMN: '2',
    'text': 'everybody'
  }])

  # Filter by a specific UUID.
  filters: list[BinaryFilterTuple] = [(UUID_COLUMN, BinaryOp.EQUALS, '1')]
  udf_col = Column('text', signal_udf=LengthSignal())
  result = dataset.select_rows(['text', udf_col], filters=filters)
  assert list(result) == [{UUID_COLUMN: '1', 'text': 'hello', 'length_signal(text)': 5}]
  assert cast(LengthSignal, udf_col.signal_udf)._call_count == 1

  filters = [(UUID_COLUMN, BinaryOp.EQUALS, '2')]
  result = dataset.select_rows(['text', udf_col], filters=filters)
  assert list(result) == [{UUID_COLUMN: '2', 'text': 'everybody', 'length_signal(text)': 9}]
  assert cast(LengthSignal, udf_col.signal_udf)._call_count == 1 + 1

  # No filters.
  result = dataset.select_rows(['text', udf_col])
  assert list(result) == [{
    UUID_COLUMN: '1',
    'text': 'hello',
    'length_signal(text)': 5
  }, {
    UUID_COLUMN: '2',
    'text': 'everybody',
    'length_signal(text)': 9
  }]
  assert cast(LengthSignal, udf_col.signal_udf)._call_count == 2 + 2


def test_udf_with_uuid_filter_repeated(make_test_data: TestDataMaker) -> None:

  dataset = make_test_data([{
    UUID_COLUMN: '1',
    'text': ['hello', 'hi']
  }, {
    UUID_COLUMN: '2',
    'text': ['everybody', 'bye', 'test']
  }])

  # Filter by a specific UUID.
  filters: list[BinaryFilterTuple] = [(UUID_COLUMN, BinaryOp.EQUALS, '1')]
  udf_col = Column(('text', '*'), signal_udf=LengthSignal())
  result = dataset.select_rows(['text', udf_col], filters=filters)
  assert list(result) == [{
    UUID_COLUMN: '1',
    'text': ['hello', 'hi'],
    'length_signal(text)': [5, 2]
  }]
  assert cast(LengthSignal, udf_col.signal_udf)._call_count == 2

  # Filter by a specific UUID.
  filters = [(UUID_COLUMN, BinaryOp.EQUALS, '2')]
  result = dataset.select_rows(['text', udf_col], filters=filters)
  assert list(result) == [{
    UUID_COLUMN: '2',
    'text': ['everybody', 'bye', 'test'],
    'length_signal(text)': [9, 3, 4]
  }]
  assert cast(LengthSignal, udf_col.signal_udf)._call_count == 2 + 3


def test_udf_deeply_nested(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data([{
    UUID_COLUMN: '1',
    'text': [['hello'], ['hi', 'bye']]
  }, {
    UUID_COLUMN: '2',
    'text': [['everybody', 'bye'], ['test']]
  }])

  udf_col = Column(('text', '*', '*'), signal_udf=LengthSignal())
  result = dataset.select_rows([udf_col])
  assert list(result) == [{
    UUID_COLUMN: '1',
    'length_signal(text.*)': [[5], [2, 3]]
  }, {
    UUID_COLUMN: '2',
    'length_signal(text.*)': [[9, 3], [4]]
  }]
  assert cast(LengthSignal, udf_col.signal_udf)._call_count == 6


def test_udf_with_embedding(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data([{
    UUID_COLUMN: '1',
    'text': 'hello.',
  }, {
    UUID_COLUMN: '2',
    'text': 'hello2.',
  }])

  dataset.compute_signal(TestEmbedding(), 'text')

  signal_col = Column('text', signal_udf=TestEmbeddingSumSignal(embedding='test_embedding'))
  result = dataset.select_rows(['text', signal_col])

  expected_result: list[Item] = [{
    UUID_COLUMN: '1',
    'text': 'hello.',
    'test_embedding_sum(text.test_embedding.*.embedding)': [1.0]
  }, {
    UUID_COLUMN: '2',
    'text': 'hello2.',
    'test_embedding_sum(text.test_embedding.*.embedding)': [2.0]
  }]
  assert list(result) == expected_result

  # Select rows with alias.
  signal_col = Column(
    'text', signal_udf=TestEmbeddingSumSignal(embedding='test_embedding'), alias='emb_sum')
  result = dataset.select_rows(['text', signal_col])
  expected_result = [{
    UUID_COLUMN: '1',
    'text': 'hello.',
    'emb_sum': [1.0]
  }, {
    UUID_COLUMN: '2',
    'text': 'hello2.',
    'emb_sum': [2.0]
  }]
  assert list(result) == expected_result


def test_udf_with_nested_embedding(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data([{
    UUID_COLUMN: '1',
    'text': ['hello.', 'hello world.'],
  }, {
    UUID_COLUMN: '2',
    'text': ['hello world2.', 'hello2.'],
  }])

  dataset.compute_signal(TestEmbedding(), ('text', '*'))

  signal_col = Column(('text', '*'), signal_udf=TestEmbeddingSumSignal(embedding='test_embedding'))
  result = dataset.select_rows([('text', '*'), signal_col])
  expected_result = [{
    UUID_COLUMN: '1',
    'text.*': ['hello.', 'hello world.'],
    'test_embedding_sum(text.*.test_embedding.*.embedding)': [[1.0], [3.0]]
  }, {
    UUID_COLUMN: '2',
    'text.*': ['hello world2.', 'hello2.'],
    'test_embedding_sum(text.*.test_embedding.*.embedding)': [[4.0], [2.0]]
  }]
  assert list(result) == expected_result


def test_udf_throws_without_precomputing(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data([{
    UUID_COLUMN: '1',
    'text': 'hello.',
  }, {
    UUID_COLUMN: '2',
    'text': 'hello2.',
  }])

  # Embedding is not precomputed, yet we ask for the embedding.

  signal_col = Column('text', signal_udf=TestEmbeddingSumSignal(embedding='test_embedding'))

  with pytest.raises(ValueError, match='Embedding signal "test_embedding" is not computed'):
    dataset.select_rows(['text', signal_col])


class TestSplitter(TextSplitterSignal):
  """Split documents into sentence by splitting on period."""
  name = 'test_splitter'

  @override
  def compute(self, data: Iterable[RichData]) -> Iterable[Item]:
    for text in data:
      if not isinstance(text, str):
        raise ValueError(f'Expected text to be a string, got {type(text)} instead.')
      result: list[Item] = []
      for sentence in text.split('.'):
        start = text.index(sentence)
        end = start + len(sentence)
        result.append(lilac_span(start, end))
      yield result


def test_udf_after_precomputed_split(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data([{
    UUID_COLUMN: '1',
    'text': 'sentence 1. sentence 2 is longer',
  }, {
    UUID_COLUMN: '2',
    'text': 'sentence 1 is longer. sent2 is short',
  }])
  dataset.compute_signal(TestSplitter(), 'text')
  udf = Column('text', signal_udf=LengthSignal())
  result = dataset.select_rows(['*', udf], combine_columns=True)
  assert list(result) == [{
    UUID_COLUMN: '1',
    'text': enriched_item('sentence 1. sentence 2 is longer', {
      'length_signal': 32,
      'test_splitter': [lilac_span(0, 10), lilac_span(11, 32)]
    })
  }, {
    UUID_COLUMN: '2',
    'text': enriched_item('sentence 1 is longer. sent2 is short', {
      'length_signal': 36,
      'test_splitter': [lilac_span(0, 20), lilac_span(21, 36)]
    })
  }]


def test_is_computed_signal_key(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data([{
    UUID_COLUMN: '1',
    'text': 'hello.',
  }, {
    UUID_COLUMN: '2',
    'text': 'hello2.',
  }])

  signal_col = Column('text', signal_udf=ComputedKeySignal())
  # Filter by source feature.
  filters: list[BinaryFilterTuple] = [('text', BinaryOp.EQUALS, 'everybody')]
  result = dataset.select_rows(['text', signal_col])
  assert list(result) == [{
    UUID_COLUMN: '1',
    'text': 'hello.',
    'key_False(text)': 1
  }, {
    UUID_COLUMN: '2',
    'text': 'hello2.',
    'key_False(text)': 1
  }]
