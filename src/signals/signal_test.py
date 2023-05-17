"""Test signal base class."""
from typing import Iterable, Optional

import pytest
from typing_extensions import override

from ..embeddings.vector_store import VectorStore
from ..schema import DataType, Field, ItemValue, RichData, SignalInputType, VectorKey, field
from .signal import (
  Signal,
  TextEmbeddingModelSignal,
  TextEmbeddingSignal,
  TextSplitterSignal,
  clear_signal_registry,
  get_signal_by_type,
  get_signal_cls,
  get_signals_by_type,
  register_signal,
  resolve_signal,
)


class TestSignal(Signal):
  """A test signal."""

  # Pydantic fields
  name = 'test_signal'
  input_type = SignalInputType.TEXT

  query: str

  @override
  def fields(self) -> Field:
    return Field(dtype=DataType.FLOAT32)

  @override
  def compute(self, data: Iterable[RichData]) -> Iterable[Optional[ItemValue]]:
    del data
    return []


class TestTextSplitter(TextSplitterSignal):
  """A test text splitter."""
  name = 'test_splitter'

  @override
  def compute(self, data: Iterable[RichData]) -> Iterable[Optional[ItemValue]]:
    del data
    return []


class TestTextEmbedding(TextEmbeddingSignal):
  """A test text embedding."""
  name = 'test_embedding'

  @override
  def compute(self, data: Iterable[RichData]) -> Iterable[Optional[ItemValue]]:
    del data
    return []


class TestTextEmbeddingModelSignal(TextEmbeddingModelSignal):
  """A test text embedding model."""
  name = 'test_embedding_model'

  @override
  def fields(self) -> Field:
    return field('float32')

  @override
  def vector_compute(self, keys: Iterable[VectorKey],
                     vector_store: VectorStore) -> Iterable[ItemValue]:
    # The signal just sums the values of the embedding.
    del keys, vector_store
    return []


@pytest.fixture(scope='module', autouse=True)
def setup_teardown() -> Iterable[None]:
  # Setup.
  register_signal(TestSignal)
  register_signal(TestTextSplitter)
  register_signal(TestTextEmbedding)
  register_signal(TestTextEmbeddingModelSignal)

  # Unit test runs.
  yield

  # Teardown.
  clear_signal_registry()


def test_signal_serialization() -> None:
  signal = TestSignal(query='test')

  # The class variables should not be included.
  assert signal.dict() == {'signal_name': 'test_signal', 'query': 'test'}


def test_get_signal_cls() -> None:
  """Test getting a signal."""
  assert TestSignal == get_signal_cls('test_signal')


def test_resolve_signal() -> None:
  """Test resolving a signal."""
  test_signal = TestSignal(query='hello')

  # Signals pass through.
  assert resolve_signal(test_signal) == test_signal

  # Dicts resolve to the base class.
  assert resolve_signal(test_signal.dict()) == test_signal


def test_get_signal_by_type() -> None:
  assert get_signal_by_type(TestTextSplitter.name, TextSplitterSignal) == TestTextSplitter
  assert get_signal_by_type(TestTextEmbedding.name, TextEmbeddingSignal) == TestTextEmbedding


def test_get_signal_by_type_validation() -> None:
  with pytest.raises(ValueError, match='Signal "invalid_signal" not found in the registry'):
    get_signal_by_type('invalid_signal', TextSplitterSignal)

  with pytest.raises(
      ValueError, match=f'"{TestTextSplitter.name}" is a `{TestTextSplitter.__name__}`'):
    get_signal_by_type(TestTextSplitter.name, TextEmbeddingSignal)


def test_get_signals_by_type() -> None:
  assert get_signals_by_type(TextSplitterSignal) == [TestTextSplitter]
  assert get_signals_by_type(TextEmbeddingSignal) == [TestTextEmbedding]


def test_signal_type_enum() -> None:
  model_signal = TestTextEmbeddingModelSignal(embedding='test_embedding')
  schema_properties = model_signal.schema()['properties']
  # Make sure the schema split enum contains the test splitter.
  assert schema_properties['split']['enum'] == [TestTextSplitter.name]
  assert schema_properties['embedding']['enum'] == [TestTextEmbedding.name]
