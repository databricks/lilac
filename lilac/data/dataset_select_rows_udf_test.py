"""Tests for dataset.select_rows(udf_col)."""

from typing import Iterable, Optional, cast

import numpy as np
import pytest
from typing_extensions import override

from ..embeddings.vector_store import VectorDBIndex
from ..schema import (
  ROWID,
  Field,
  Item,
  RichData,
  SignalInputType,
  VectorKey,
  field,
  lilac_embedding,
  lilac_span,
)
from ..signal import (
  TextEmbeddingSignal,
  TextSignal,
  TextSplitterSignal,
  VectorSignal,
  clear_signal_registry,
  register_signal,
)
from .dataset import BinaryFilterTuple, Column
from .dataset_test_utils import TestDataMaker, enriched_item

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


class TestEmbeddingSumSignal(VectorSignal):
  """Sums the embeddings to return a single floating point value."""
  name = 'test_embedding_sum'
  input_type = SignalInputType.TEXT

  @override
  def fields(self) -> Field:
    return field('float32')

  @override
  def vector_compute(self, keys: Iterable[VectorKey],
                     vector_index: VectorDBIndex) -> Iterable[Item]:
    # The signal just sums the values of the embedding.
    all_vector_spans = vector_index.get(keys)
    for vector_spans in all_vector_spans:
      yield vector_spans[0]['vector'].sum()


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
  dataset = make_test_data([{'text': 'hello'}, {'text': 'everybody'}])

  signal_col = Column('text', signal_udf=TestSignal())
  result = dataset.select_rows(['text', signal_col])

  assert list(result) == [{
    'text': 'hello',
    'text.test_signal': {
      'len': 5,
      'flen': 5.0
    }
  }, {
    'text': 'everybody',
    'text.test_signal': {
      'len': 9,
      'flen': 9.0
    }
  }]


def test_udf_with_filters(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data([{'text': 'hello'}, {'text': 'everybody'}])

  signal_col = Column('text', signal_udf=TestSignal())
  # Filter by source feature.
  filters: list[BinaryFilterTuple] = [('text', 'equals', 'everybody')]
  result = dataset.select_rows(['text', signal_col], filters=filters)
  assert list(result) == [{'text': 'everybody', 'text.test_signal': {'len': 9, 'flen': 9.0}}]


def test_udf_with_rowid_filter(make_test_data: TestDataMaker) -> None:

  dataset = make_test_data([{'text': 'hello'}, {'text': 'everybody'}])

  # Filter by a specific rowid.
  filters: list[BinaryFilterTuple] = [(ROWID, 'equals', '1')]
  udf_col = Column('text', signal_udf=LengthSignal())
  result = dataset.select_rows([ROWID, 'text', udf_col], filters=filters)
  assert list(result) == [{ROWID: '1', 'text': 'hello', 'text.length_signal': 5}]
  assert cast(LengthSignal, udf_col.signal_udf)._call_count == 1

  filters = [(ROWID, 'equals', '2')]
  result = dataset.select_rows([ROWID, 'text', udf_col], filters=filters)
  assert list(result) == [{ROWID: '2', 'text': 'everybody', 'text.length_signal': 9}]
  assert cast(LengthSignal, udf_col.signal_udf)._call_count == 1 + 1

  # No filters.
  result = dataset.select_rows([ROWID, 'text', udf_col])
  assert list(result) == [{
    ROWID: '1',
    'text': 'hello',
    'text.length_signal': 5
  }, {
    ROWID: '2',
    'text': 'everybody',
    'text.length_signal': 9
  }]
  assert cast(LengthSignal, udf_col.signal_udf)._call_count == 2 + 2


def test_udf_with_rowid_filter_repeated(make_test_data: TestDataMaker) -> None:

  dataset = make_test_data([{'text': ['hello', 'hi']}, {'text': ['everybody', 'bye', 'test']}])

  # Filter by a specific rowid.
  filters: list[BinaryFilterTuple] = [(ROWID, 'equals', '1')]
  udf_col = Column(('text', '*'), signal_udf=LengthSignal())
  result = dataset.select_rows([ROWID, 'text', udf_col], filters=filters)
  assert list(result) == [{ROWID: '1', 'text': ['hello', 'hi'], 'text.length_signal': [5, 2]}]
  assert cast(LengthSignal, udf_col.signal_udf)._call_count == 2

  # Filter by a specific rowid.
  filters = [(ROWID, 'equals', '2')]
  result = dataset.select_rows([ROWID, 'text', udf_col], filters=filters)
  assert list(result) == [{
    ROWID: '2',
    'text': ['everybody', 'bye', 'test'],
    'text.length_signal': [9, 3, 4]
  }]
  assert cast(LengthSignal, udf_col.signal_udf)._call_count == 2 + 3


def test_udf_deeply_nested(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data([{
    'text': [['hello'], ['hi', 'bye']]
  }, {
    'text': [['everybody', 'bye'], ['test']]
  }])

  udf_col = Column(('text', '*', '*'), signal_udf=LengthSignal())
  result = dataset.select_rows([udf_col])
  assert list(result) == [{
    'text.length_signal': [[5], [2, 3]]
  }, {
    'text.length_signal': [[9, 3], [4]]
  }]
  assert cast(LengthSignal, udf_col.signal_udf)._call_count == 6


def test_udf_with_embedding(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data([{
    'text': 'hello.',
  }, {
    'text': 'hello2.',
  }])

  dataset.compute_signal(TestEmbedding(), 'text')

  signal_col = Column('text', signal_udf=TestEmbeddingSumSignal(embedding='test_embedding'))
  result = dataset.select_rows(['text', signal_col])

  expected_result: list[Item] = [{
    'text': 'hello.',
    'text.test_embedding_sum(embedding=test_embedding)': 1.0
  }, {
    'text': 'hello2.',
    'text.test_embedding_sum(embedding=test_embedding)': 2.0
  }]
  assert list(result) == expected_result

  # Select rows with alias.
  signal_col = Column(
    'text', signal_udf=TestEmbeddingSumSignal(embedding='test_embedding'), alias='emb_sum')
  result = dataset.select_rows(['text', signal_col])
  expected_result = [{'text': 'hello.', 'emb_sum': 1.0}, {'text': 'hello2.', 'emb_sum': 2.0}]
  assert list(result) == expected_result


def test_udf_with_nested_embedding(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data([{
    'text': ['hello.', 'hello world.'],
  }, {
    'text': ['hello world2.', 'hello2.'],
  }])

  dataset.compute_signal(TestEmbedding(), ('text', '*'))

  signal_col = Column(('text', '*'), signal_udf=TestEmbeddingSumSignal(embedding='test_embedding'))
  result = dataset.select_rows([('text', '*'), signal_col])
  expected_result = [{
    'text.*': ['hello.', 'hello world.'],
    'text.test_embedding_sum(embedding=test_embedding)': [1.0, 3.0]
  }, {
    'text.*': ['hello world2.', 'hello2.'],
    'text.test_embedding_sum(embedding=test_embedding)': [4.0, 2.0]
  }]
  assert list(result) == expected_result


def test_udf_throws_without_precomputing(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data([{
    'text': 'hello.',
  }, {
    'text': 'hello2.',
  }])

  # Embedding is not precomputed, yet we ask for the embedding.

  signal_col = Column('text', signal_udf=TestEmbeddingSumSignal(embedding='test_embedding'))

  with pytest.raises(ValueError, match="No embedding found for path \\('text',\\)"):
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
    'text': 'sentence 1. sentence 2 is longer',
  }, {
    'text': 'sentence 1 is longer. sent2 is short',
  }])
  dataset.compute_signal(TestSplitter(), 'text')
  udf = Column('text', signal_udf=LengthSignal())
  result = dataset.select_rows(['*', udf], combine_columns=True)
  assert list(result) == [{
    'text': enriched_item('sentence 1. sentence 2 is longer', {
      'length_signal': 32,
      'test_splitter': [lilac_span(0, 10), lilac_span(11, 32)]
    })
  }, {
    'text': enriched_item('sentence 1 is longer. sent2 is short', {
      'length_signal': 36,
      'test_splitter': [lilac_span(0, 20), lilac_span(21, 36)]
    })
  }]


def test_is_computed_signal_key(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data([{
    'text': 'hello.',
  }, {
    'text': 'hello2.',
  }])

  signal_col = Column('text', signal_udf=ComputedKeySignal())
  result = dataset.select_rows(['text', signal_col])
  assert list(result) == [{
    'text': 'hello.',
    'text.key_False': 1
  }, {
    'text': 'hello2.',
    'text.key_False': 1
  }]
