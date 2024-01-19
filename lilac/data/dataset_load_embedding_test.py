"""Tests for dataset.load_embedding()."""

from typing import Iterable

import numpy as np
import pytest

from ..schema import (
  EMBEDDING_KEY,
  ROWID,
  SPAN_KEY,
  Item,
  chunk_embedding,
  field,
  schema,
  span,
)
from ..signal import clear_signal_registry, create_user_text_embedding_signal
from ..source import clear_source_registry, register_source
from .dataset import DatasetManifest
from .dataset_test_utils import (
  TEST_DATASET_NAME,
  TEST_NAMESPACE,
  TestDataMaker,
  TestSource,
)

EMBEDDINGS: dict[str, list[float]] = {
  '1': [1.0, 0.0, 0.0],
  '2': [1.0, 1.0, 0.0],
  '3': [0.0, 0.0, 1.0],
}


ITEMS: list[Item] = [
  {'id': '1', 'str': 'hello.'},
  {'id': '2', 'str': 'hello2.'},
  {'id': '3', 'str': 'hello3.'},
]


@pytest.fixture(scope='module', autouse=True)
def setup_teardown() -> Iterable[None]:
  # Setup.
  clear_signal_registry()
  register_source(TestSource)

  # Unit test runs.
  yield

  # Teardown.
  clear_source_registry()
  clear_signal_registry()


def test_load_embedding_full_doc(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data(ITEMS)

  def _load_embedding(item: Item) -> np.ndarray:
    # Return a full-doc np.array embedding.
    return np.array(EMBEDDINGS[item['id']])

  dataset.load_embedding(_load_embedding, index_path='str', embedding_name='test_embedding')

  embedding_signal = create_user_text_embedding_signal('test_embedding')
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

  rows = dataset.select_rows(combine_columns=True)
  assert list(rows) == ITEMS

  # Make sure the row-level embeddings match the embeddings we explicitly passed.
  rows = list(dataset.select_rows(['*', ROWID]))
  assert len(rows) == 3
  for row in rows:
    embeddings = dataset.get_embeddings('test_embedding', row[ROWID], 'str')
    assert len(embeddings) == 1
    embedding = embeddings[0]

    np.testing.assert_array_almost_equal(embedding[EMBEDDING_KEY], EMBEDDINGS[row['id']])
    assert embedding[SPAN_KEY] == span(0, len(row['str']))[SPAN_KEY]


def test_load_embedding_chunks(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data(ITEMS)

  def _load_embedding(item: Item) -> list[Item]:
    return [
      chunk_embedding(0, 1, np.array(EMBEDDINGS[item['id']])),
      chunk_embedding(1, 2, 2 * np.array(EMBEDDINGS[item['id']])),
    ]

  dataset.load_embedding(_load_embedding, index_path='str', embedding_name='test_embedding')

  embedding_signal = create_user_text_embedding_signal('test_embedding')
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

  rows = dataset.select_rows(combine_columns=True)
  assert list(rows) == ITEMS

  # Make sure the row-level embeddings match the embeddings we explicitly passed.
  rows = list(dataset.select_rows(['*', ROWID]))
  assert len(rows) == 3
  for row in rows:
    embeddings = dataset.get_embeddings('test_embedding', row[ROWID], 'str')
    assert len(embeddings) == 2

    np.testing.assert_array_almost_equal(embeddings[0][EMBEDDING_KEY], EMBEDDINGS[row['id']])
    assert embeddings[0][SPAN_KEY] == span(0, 1)[SPAN_KEY]

    np.testing.assert_array_almost_equal(
      embeddings[1][EMBEDDING_KEY], [2 * x for x in EMBEDDINGS[row['id']]]
    )
    assert embeddings[1][SPAN_KEY] == span(1, 2)[SPAN_KEY]


def test_load_embedding_overwrite(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data(ITEMS)

  multiplier = 1.0

  def _load_embedding(item: Item) -> np.ndarray:
    # Return a full-doc np.array embedding.
    return multiplier * np.array(EMBEDDINGS[item['id']])

  # Call load_embedding once.
  dataset.load_embedding(_load_embedding, index_path='str', embedding_name='test_embedding')

  # Make sure the row-level embeddings match the embeddings we explicitly passed.
  rows = list(dataset.select_rows(['*', ROWID]))
  assert len(rows) == 3
  for row in rows:
    [embedding] = dataset.get_embeddings('test_embedding', row[ROWID], 'str')

    np.testing.assert_array_almost_equal(embedding[EMBEDDING_KEY], EMBEDDINGS[row['id']])

  multiplier = 2.0

  # Call load_embedding again with overwrite=True.
  dataset.load_embedding(
    _load_embedding, index_path='str', embedding_name='test_embedding', overwrite=True
  )

  # Make sure the row-level embeddings match the embeddings we explicitly passed, times 2.
  rows = list(dataset.select_rows(['*', ROWID]))
  assert len(rows) == 3
  for row in rows:
    [embedding] = dataset.get_embeddings('test_embedding', row[ROWID], 'str')
    print('get_embeddings=', embedding)

    np.testing.assert_array_almost_equal(
      embedding[EMBEDDING_KEY], [multiplier * x for x in EMBEDDINGS[row['id']]]
    )


def test_load_embedding_throws_twice_no_overwrite(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data(ITEMS)

  multiplier = 1.0

  def _load_embedding(item: Item) -> np.ndarray:
    # Return a full-doc np.array embedding.
    return multiplier * np.array(EMBEDDINGS[item['id']])

  # Call load_embedding once.
  dataset.load_embedding(_load_embedding, index_path='str', embedding_name='test_embedding')

  # Make sure the row-level embeddings match the embeddings we explicitly passed.
  rows = list(dataset.select_rows(['*', ROWID]))
  assert len(rows) == 3
  for row in rows:
    [embedding] = dataset.get_embeddings('test_embedding', row[ROWID], 'str')

    np.testing.assert_array_almost_equal(embedding[EMBEDDING_KEY], EMBEDDINGS[row['id']])

  # Calling load_embedding again with the same embedding name throws.
  with pytest.raises(ValueError, match='blah blah'):
    dataset.load_embedding(_load_embedding, index_path='str', embedding_name='test_embedding')
