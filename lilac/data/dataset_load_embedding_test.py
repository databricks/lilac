"""Tests for dataset.load_embedding()."""

import re
from typing import ClassVar, Iterable, Iterator, Union, cast

import numpy as np
import pytest
from typing_extensions import override

from ..schema import (
  EMBEDDING_KEY,
  ROWID,
  SPAN_KEY,
  Item,
  RichData,
  chunk_embedding,
  field,
  schema,
  span,
)
from ..signal import TextEmbeddingSignal, clear_signal_registry, register_embedding
from ..source import clear_source_registry, register_source
from .dataset import DatasetManifest
from .dataset_test_utils import (
  TEST_DATASET_NAME,
  TEST_NAMESPACE,
  TestDataMaker,
  TestSource,
)

ID_EMBEDDINGS: dict[str, list[float]] = {
  '1': [1.0, 0.0, 0.0],
  # This embedding has an outer dimension of 1.
  '2': [1.0, 1.0, 0.0],
  '3': [0.0, 0.0, 1.0],
}

EMBEDDINGS: list[tuple[str, Union[list[float], list[list[float]]]]] = [
  ('hello.', ID_EMBEDDINGS['1']),
  ('hello2.', ID_EMBEDDINGS['2']),
  ('hello3.', ID_EMBEDDINGS['3']),
]

STR_EMBEDDINGS: dict[str, Union[list[float], list[list[float]]]] = {
  text: embedding for text, embedding in EMBEDDINGS
}

ITEMS: list[Item] = [
  {'id': '1', 'str': 'hello.'},
  {'id': '2', 'str': 'hello2.'},
  {'id': '3', 'str': 'hello3.'},
]


class TestEmbedding(TextEmbeddingSignal):
  """A test embed function."""

  name: ClassVar[str] = 'test_embedding'

  @override
  def compute(self, data: Iterable[RichData]) -> Iterator[Item]:
    """Call the embedding function."""
    for example in data:
      example = cast(str, example)
      yield [chunk_embedding(0, len(example), np.array(STR_EMBEDDINGS[example]))]


@pytest.fixture(scope='module', autouse=True)
def setup_teardown() -> Iterable[None]:
  # Setup.
  clear_signal_registry()
  register_source(TestSource)
  register_embedding(TestEmbedding)

  # Unit test runs.
  yield

  # Teardown.
  clear_source_registry()
  clear_signal_registry()


def test_load_embedding_full_doc(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data(ITEMS)

  def _load_embedding(item: Item) -> np.ndarray:
    # Return a full-doc np.array embedding.
    return np.array(ID_EMBEDDINGS[item['id']])

  dataset.load_embedding(_load_embedding, index_path='str', embedding='test_embedding')

  embedding_signal = TestEmbedding()
  assert dataset.manifest() == DatasetManifest(
    namespace=TEST_NAMESPACE,
    dataset_name=TEST_DATASET_NAME,
    data_schema=schema(
      {
        'id': 'string',
        'str': field(
          'string',
          fields={
            'test_embedding': field(
              signal=embedding_signal.model_dump(exclude_none=True),
              fields=[field('string_span', fields={EMBEDDING_KEY: 'embedding'})],
            )
          },
        ),
      }
    ),
    num_items=3,
    source=TestSource(),
  )

  rows = list(dataset.select_rows(combine_columns=True))
  assert rows == ITEMS

  # Make sure the row-level embeddings match the embeddings we explicitly passed.
  rows = list(dataset.select_rows(['*', ROWID]))
  assert len(rows) == 3
  for row in rows:
    embeddings = dataset.get_embeddings('test_embedding', row[ROWID], 'str')
    assert len(embeddings) == 1
    embedding = embeddings[0]

    np.testing.assert_array_almost_equal(
      embedding[EMBEDDING_KEY], np.array(ID_EMBEDDINGS[row['id']], dtype=np.float32)
    )
    assert embedding[SPAN_KEY] == span(0, len(row['str']))[SPAN_KEY]


def test_load_embedding_chunks(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data(ITEMS)

  def _load_embedding(item: Item) -> list[Item]:
    return [
      chunk_embedding(0, 1, np.array(ID_EMBEDDINGS[item['id']])),
      chunk_embedding(1, 2, 2 * np.array(ID_EMBEDDINGS[item['id']])),
    ]

  dataset.load_embedding(_load_embedding, index_path='str', embedding='test_embedding')

  embedding_signal = TestEmbedding()
  assert dataset.manifest() == DatasetManifest(
    namespace=TEST_NAMESPACE,
    dataset_name=TEST_DATASET_NAME,
    data_schema=schema(
      {
        'id': 'string',
        'str': field(
          'string',
          fields={
            'test_embedding': field(
              signal=embedding_signal.model_dump(exclude_none=True),
              fields=[field('string_span', fields={EMBEDDING_KEY: 'embedding'})],
            )
          },
        ),
      }
    ),
    num_items=3,
    source=TestSource(),
  )

  rows = list(dataset.select_rows(combine_columns=True))
  assert rows == ITEMS

  # Make sure the row-level embeddings match the embeddings we explicitly passed.
  rows = list(dataset.select_rows(['*', ROWID]))
  assert len(rows) == 3
  for row in rows:
    embeddings = dataset.get_embeddings('test_embedding', row[ROWID], 'str')
    assert len(embeddings) == 2

    np.testing.assert_array_almost_equal(
      embeddings[0][EMBEDDING_KEY], np.array(ID_EMBEDDINGS[row['id']], dtype=np.float32)
    )
    assert embeddings[0][SPAN_KEY] == span(0, 1)[SPAN_KEY]

    np.testing.assert_array_almost_equal(
      embeddings[1][EMBEDDING_KEY],
      np.array([2 * x for x in ID_EMBEDDINGS[row['id']]], dtype=np.float32),
    )

    assert embeddings[1][SPAN_KEY] == span(1, 2)[SPAN_KEY]


def test_load_embedding_overwrite(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data(ITEMS)

  multiplier = 1.0

  def _load_embedding(item: Item) -> np.ndarray:
    # Return a full-doc np.array embedding.
    return multiplier * np.array(ID_EMBEDDINGS[item['id']])

  # Call load_embedding once.
  dataset.load_embedding(_load_embedding, index_path='str', embedding='test_embedding')

  # Make sure the row-level embeddings match the embeddings we explicitly passed.
  rows = list(dataset.select_rows(['*', ROWID]))
  assert len(rows) == 3
  for row in rows:
    [embedding] = dataset.get_embeddings('test_embedding', row[ROWID], 'str')

    np.testing.assert_array_almost_equal(
      embedding[EMBEDDING_KEY], np.array(ID_EMBEDDINGS[row['id']], dtype=np.float32)
    )

  multiplier = 2.0

  # Call load_embedding again with overwrite=True.
  dataset.load_embedding(
    _load_embedding, index_path='str', embedding='test_embedding', overwrite=True
  )

  # Make sure the row-level embeddings match the embeddings we explicitly passed, times 2.
  rows = list(dataset.select_rows(['*', ROWID]))
  assert len(rows) == 3
  for row in rows:
    [embedding] = dataset.get_embeddings('test_embedding', row[ROWID], 'str')

    np.testing.assert_array_almost_equal(
      embedding[EMBEDDING_KEY], [multiplier * x for x in ID_EMBEDDINGS[row['id']]]
    )


def test_load_embedding_throws_twice_no_overwrite(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data(ITEMS)

  multiplier = 1.0

  def _load_embedding(item: Item) -> np.ndarray:
    # Return a full-doc np.array embedding.
    return multiplier * np.array(ID_EMBEDDINGS[item['id']])

  # Call load_embedding once.
  dataset.load_embedding(_load_embedding, index_path='str', embedding='test_embedding')

  # Make sure the row-level embeddings match the embeddings we explicitly passed.
  rows = list(dataset.select_rows(['*', ROWID]))
  assert len(rows) == 3
  for row in rows:
    [embedding] = dataset.get_embeddings('test_embedding', row[ROWID], 'str')

    np.testing.assert_array_almost_equal(
      embedding[EMBEDDING_KEY], np.array(ID_EMBEDDINGS[row['id']], dtype=np.float32)
    )

  # Calling load_embedding again with the same embedding name throws.
  with pytest.raises(
    ValueError,
    match=re.escape(
      'Embedding "test_embedding" already exists at path (\'str\',). '
      'Use overwrite=True to overwrite.'
    ),
  ):
    dataset.load_embedding(_load_embedding, index_path='str', embedding='test_embedding')


def test_load_embedding_no_registered_embed(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data(ITEMS)

  def _load_embedding(item: Item) -> np.ndarray:
    # Return a full-doc np.array embedding.
    return np.array(ID_EMBEDDINGS[item['id']])

  # Call load_embedding once.
  with pytest.raises(
    ValueError,
    match=re.escape('Embedding "other_embedding" not found. You must register an embedding'),
  ):
    dataset.load_embedding(_load_embedding, index_path='str', embedding='other_embedding')
