"""Tests for dataset.compute_signal() when signals are chained."""

import re
from typing import ClassVar, Iterable, List, Optional, cast

import numpy as np
import pytest
from pytest_mock import MockerFixture
from typing_extensions import override

from ..embeddings.vector_store import VectorDBIndex
from ..schema import (
  EMBEDDING_KEY,
  Field,
  Item,
  PathKey,
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
  VectorSignal,
  clear_signal_registry,
  register_signal,
)
from ..source import clear_source_registry, register_source
from .dataset import DatasetManifest
from .dataset_test_utils import (
  TEST_DATASET_NAME,
  TEST_NAMESPACE,
  TestDataMaker,
  TestSource,
  enriched_item,
)

SIMPLE_ITEMS: list[Item] = [
  {'str': 'a', 'int': 1, 'bool': False, 'float': 3.0},
  {'str': 'b', 'int': 2, 'bool': True, 'float': 2.0},
  {'str': 'b', 'int': 2, 'bool': True, 'float': 1.0},
]

EMBEDDINGS: list[tuple[str, list[float]]] = [
  ('hello.', [1.0, 0.0, 0.0]),
  ('hello2.', [1.0, 1.0, 0.0]),
  ('hello world.', [1.0, 1.0, 1.0]),
  ('hello world2.', [2.0, 1.0, 1.0]),
]

STR_EMBEDDINGS: dict[str, list[float]] = {text: embedding for text, embedding in EMBEDDINGS}


class TestSplitter(TextSignal):
  """Split documents into sentence by splitting on period."""

  name: ClassVar[str] = 'test_splitter'

  @override
  def fields(self) -> Field:
    return field(fields=['string_span'])

  @override
  def compute(self, data: Iterable[RichData]) -> Iterable[Item]:
    for text in data:
      if not isinstance(text, str):
        raise ValueError(f'Expected text to be a string, got {type(text)} instead.')
      sentences = [f'{sentence.strip()}.' for sentence in text.split('.') if sentence]
      yield [
        lilac_span(text.index(sentence), text.index(sentence) + len(sentence))
        for sentence in sentences
      ]


class TestEmbedding(TextEmbeddingSignal):
  """A test embed function."""

  name: ClassVar[str] = 'test_embedding'

  @override
  def compute(self, data: Iterable[RichData]) -> Iterable[Item]:
    """Call the embedding function."""
    for example in data:
      yield [lilac_embedding(0, len(example), np.array(STR_EMBEDDINGS[cast(str, example)]))]


class TestEmbeddingSumSignal(VectorSignal):
  """Sums the embeddings to return a single floating point value."""

  name: ClassVar[str] = 'test_embedding_sum'
  input_type: ClassVar[SignalInputType] = SignalInputType.TEXT

  @override
  def fields(self) -> Field:
    return field('float32')

  @override
  def vector_compute(self, keys: Iterable[PathKey], vector_index: VectorDBIndex) -> Iterable[Item]:
    # The signal just sums the values of the embedding.
    all_vector_spans = vector_index.get(keys)
    for vector_spans in all_vector_spans:
      yield float(vector_spans[0]['vector'].sum())


@pytest.fixture(scope='module', autouse=True)
def setup_teardown() -> Iterable[None]:
  # Setup.
  register_source(TestSource)
  register_signal(TestSplitter)
  register_signal(TestEmbedding)
  register_signal(TestEmbeddingSumSignal)
  register_signal(NamedEntity)
  # Unit test runs.
  yield
  # Teardown.
  clear_source_registry()
  clear_signal_registry()


def test_manual_embedding_signal(make_test_data: TestDataMaker, mocker: MockerFixture) -> None:
  dataset = make_test_data([{'text': 'hello.'}, {'text': 'hello2.'}])

  embed_mock = mocker.spy(TestEmbedding, 'compute')
  dataset.compute_embedding('test_embedding', 'text')
  embedding_sum_signal = TestEmbeddingSumSignal(embedding='test_embedding')
  dataset.compute_signal(embedding_sum_signal, 'text')

  # Make sure the embedding signal is not called twice.
  assert embed_mock.call_count == 1

  assert dataset.manifest() == DatasetManifest(
    namespace=TEST_NAMESPACE,
    dataset_name=TEST_DATASET_NAME,
    data_schema=schema(
      {
        'text': field(
          'string',
          fields={
            'test_embedding_sum(embedding=test_embedding)': field(
              'float32', signal=embedding_sum_signal.model_dump()
            ),
            'test_embedding': field(
              signal=TestEmbedding().model_dump(),
              fields=[field('string_span', fields={EMBEDDING_KEY: 'embedding'})],
            ),
          },
        )
      }
    ),
    num_items=2,
    source=TestSource(),
  )

  result = dataset.select_rows(combine_columns=True)
  expected_result = [
    {'text': enriched_item('hello.', {'test_embedding_sum(embedding=test_embedding)': 1.0})},
    {'text': enriched_item('hello2.', {'test_embedding_sum(embedding=test_embedding)': 2.0})},
  ]
  assert list(result) == expected_result


def test_missing_embedding_signal(make_test_data: TestDataMaker, mocker: MockerFixture) -> None:
  dataset = make_test_data([{'text': 'hello.'}, {'text': 'hello2.'}])

  # The embedding is missing for 'text'.
  embedding_sum_signal = TestEmbeddingSumSignal(embedding=TestEmbedding.name)
  with pytest.raises(ValueError, match="No embedding found for path \\('text',\\)"):
    dataset.compute_signal(embedding_sum_signal, 'text')


ENTITY_REGEX = r'[A-Za-z]+@[A-Za-z]+'


class NamedEntity(TextSignal):
  """Find special entities."""

  name: ClassVar[str] = 'entity'

  @override
  def fields(self) -> Field:
    return field(fields=['string_span'])

  @override
  def compute(self, data: Iterable[RichData]) -> Iterable[Optional[List[Item]]]:
    for text in data:
      if not isinstance(text, str):
        yield None
        continue
      yield [lilac_span(m.start(0), m.end(0)) for m in re.finditer(ENTITY_REGEX, text)]
