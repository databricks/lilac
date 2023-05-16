"""Tests for dataset.select_rows(udf_col)."""

from typing import Iterable, Optional, cast

import numpy as np
import pytest
from typing_extensions import override

from ..embeddings.vector_store import VectorStore
from ..schema import (
  UUID_COLUMN,
  VALUE_KEY,
  Field,
  Item,
  ItemValue,
  PathTuple,
  RichData,
  SignalOut,
  field,
  signal_field,
)
from ..signals.signal import (
  TextEmbeddingModelSignal,
  TextEmbeddingSignal,
  TextSignal,
  clear_signal_registry,
  register_signal,
)
from .dataset import BinaryFilterTuple, BinaryOp, Column, val
from .dataset_test_utils import TestDataMaker
from .dataset_utils import lilac_item, lilac_items, signal_item

EMBEDDINGS: list[tuple[str, list[float]]] = [('hello.', [1.0, 0.0, 0.0]),
                                             ('hello2.', [1.0, 1.0, 0.0]),
                                             ('hello world.', [1.0, 1.0, 1.0]),
                                             ('hello world2.', [2.0, 1.0, 1.0])]

STR_EMBEDDINGS: dict[str, list[float]] = {text: embedding for text, embedding in EMBEDDINGS}


class TestEmbedding(TextEmbeddingSignal):
  """A test embed function."""
  name = 'test_embedding'

  @override
  def fields(self) -> Field:
    """Return the fields for the embedding."""
    return signal_field(dtype='embedding', metadata={'neg_sum': 'float32'})

  @override
  def compute(self, data: Iterable[RichData]) -> Iterable[Item]:
    """Call the embedding function."""
    embeddings = [np.array(STR_EMBEDDINGS[cast(str, example)]) for example in data]
    yield from (signal_item(e, metadata={'neg_sum': -1 * e.sum()}) for e in embeddings)


class LengthSignal(TextSignal):
  name = 'length_signal'

  _call_count: int = 0

  def fields(self) -> Field:
    return field('int32')

  def compute(self, data: Iterable[RichData]) -> Iterable[Optional[SignalOut]]:
    for text_content in data:
      self._call_count += 1
      yield len(text_content)


class TestSignal(TextSignal):
  name = 'test_signal'

  @override
  def fields(self) -> Field:
    return field({'len': 'int32', 'flen': 'float32'})

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
  def vector_compute(self, keys: Iterable[PathTuple],
                     vector_store: VectorStore) -> Iterable[ItemValue]:
    # The signal just sums the values of the embedding.
    embedding_sums = vector_store.get(keys).sum(axis=1)
    for embedding_sum in embedding_sums.tolist():
      yield embedding_sum


@pytest.fixture(scope='module', autouse=True)
def setup_teardown() -> Iterable[None]:
  # Setup.
  register_signal(LengthSignal)
  register_signal(TestEmbedding)
  register_signal(TestSignal)
  register_signal(TestEmbeddingSumSignal)
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

  assert list(result) == lilac_items([{
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
  }])


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
  assert list(result) == lilac_items([{
    UUID_COLUMN: '2',
    'text': 'everybody',
    'test_signal(text)': {
      'len': 9,
      'flen': 9.0
    }
  }])


def test_udf_with_uuid_filter(make_test_data: TestDataMaker) -> None:

  dataset = make_test_data([{
    UUID_COLUMN: '1',
    'text': 'hello'
  }, {
    UUID_COLUMN: '2',
    'text': 'everybody'
  }])

  signal = LengthSignal()
  # Filter by a specific UUID.
  filters: list[BinaryFilterTuple] = [(UUID_COLUMN, BinaryOp.EQUALS, '1')]
  result = dataset.select_rows(['text', Column('text', signal_udf=signal)], filters=filters)
  assert list(result) == lilac_items([{
    UUID_COLUMN: '1',
    'text': 'hello',
    'length_signal(text)': 5
  }])
  assert signal._call_count == 1

  filters = [(UUID_COLUMN, BinaryOp.EQUALS, '2')]
  result = dataset.select_rows(['text', Column('text', signal_udf=signal)], filters=filters)
  assert list(result) == lilac_items([{
    UUID_COLUMN: '2',
    'text': 'everybody',
    'length_signal(text)': 9
  }])
  assert signal._call_count == 1 + 1

  # No filters.
  result = dataset.select_rows(['text', Column('text', signal_udf=signal)])
  assert list(result) == lilac_items([{
    UUID_COLUMN: '1',
    'text': 'hello',
    'length_signal(text)': 5
  }, {
    UUID_COLUMN: '2',
    'text': 'everybody',
    'length_signal(text)': 9
  }])
  assert signal._call_count == 2 + 2


def test_udf_with_uuid_filter_repeated(make_test_data: TestDataMaker) -> None:

  dataset = make_test_data([{
    UUID_COLUMN: '1',
    'text': ['hello', 'hi']
  }, {
    UUID_COLUMN: '2',
    'text': ['everybody', 'bye', 'test']
  }])

  signal = LengthSignal()

  # Filter by a specific UUID.
  filters: list[BinaryFilterTuple] = [(UUID_COLUMN, BinaryOp.EQUALS, '1')]
  result = dataset.select_rows(['text', Column(('text', '*'), signal_udf=signal)], filters=filters)
  assert list(result) == lilac_items([{
    UUID_COLUMN: '1',
    'text': ['hello', 'hi'],
    'length_signal(text)': [5, 2]
  }])
  assert signal._call_count == 2

  # Filter by a specific UUID.
  filters = [(UUID_COLUMN, BinaryOp.EQUALS, '2')]
  result = dataset.select_rows(['text', Column(('text', '*'), signal_udf=signal)], filters=filters)
  assert list(result) == lilac_items([{
    UUID_COLUMN: '2',
    'text': ['everybody', 'bye', 'test'],
    'length_signal(text)': [9, 3, 4]
  }])
  assert signal._call_count == 2 + 3


def test_udf_deeply_nested(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data([{
    UUID_COLUMN: '1',
    'text': [['hello'], ['hi', 'bye']]
  }, {
    UUID_COLUMN: '2',
    'text': [['everybody', 'bye'], ['test']]
  }])

  signal = LengthSignal()

  result = dataset.select_rows([Column(('text', '*', '*'), signal_udf=signal)])
  assert list(result) == lilac_items([{
    UUID_COLUMN: '1',
    'length_signal(text.*)': [[5], [2, 3]]
  }, {
    UUID_COLUMN: '2',
    'length_signal(text.*)': [[9, 3], [4]]
  }])
  assert signal._call_count == 6


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
  result = dataset.select_rows([val('text'), signal_col])

  expected_result: list[Item] = [{
    UUID_COLUMN: '1',
    f'text.{VALUE_KEY}': 'hello.',
    'test_embedding_sum(text.test_embedding)': lilac_item(1.0)
  }, {
    UUID_COLUMN: '2',
    f'text.{VALUE_KEY}': 'hello2.',
    'test_embedding_sum(text.test_embedding)': lilac_item(2.0)
  }]
  assert list(result) == expected_result

  # Select rows with alias.
  signal_col = Column(
    'text', signal_udf=TestEmbeddingSumSignal(embedding='test_embedding'), alias='emb_sum')
  result = dataset.select_rows([val('text'), signal_col])
  expected_result = [{
    UUID_COLUMN: '1',
    f'text.{VALUE_KEY}': 'hello.',
    'emb_sum': lilac_item(1.0)
  }, {
    UUID_COLUMN: '2',
    f'text.{VALUE_KEY}': 'hello2.',
    'emb_sum': lilac_item(2.0)
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
  result = dataset.select_rows([val(('text', '*')), signal_col])
  expected_result = [{
    UUID_COLUMN: '1',
    f'text.*.{VALUE_KEY}': ['hello.', 'hello world.'],
    'test_embedding_sum(text.*.test_embedding)': lilac_items([1.0, 3.0])
  }, {
    UUID_COLUMN: '2',
    f'text.*.{VALUE_KEY}': ['hello world2.', 'hello2.'],
    'test_embedding_sum(text.*.test_embedding)': lilac_items([4.0, 2.0])
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
    dataset.select_rows([val('text'), signal_col])
