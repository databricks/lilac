"""Tests for embedding indexers."""

import pathlib
import sys
from typing import Iterable, Type, cast

import numpy as np
import pytest
from pytest_mock import MockerFixture

from ..schema import RichData
from .embedding_index import EmbeddingIndexer
from .embedding_index_disk import EmbeddingIndexerDisk
from .embedding_registry import clear_embedding_registry, register_embed_fn

ALL_INDEXERS: list[Type[EmbeddingIndexer]] = [EmbeddingIndexerDisk]

TEST_EMBEDDING_NAME = 'test_embedding'

EMBEDDINGS: list[tuple[bytes, str, list[float]]] = [(b'1', 'hello', [1.0, 0.0, 0.0]),
                                                    (b'2', 'hello world', [0.9, 0.1, 0.0]),
                                                    (b'3', 'far', [0.0, 0.0, 1.0])]

STR_EMBEDDINGS: dict[str, list[float]] = {text: embedding for _, text, embedding in EMBEDDINGS}
KEY_EMBEDDINGS: dict[bytes, list[float]] = {key: embedding for key, _, embedding in EMBEDDINGS}


@pytest.fixture(scope='module', autouse=True)
def setup_teardown() -> Iterable[None]:

  # We register the embed function like this so we can mock it and assert how many times its called.
  register_embed_fn(TEST_EMBEDDING_NAME)(lambda examples: embed(examples))

  # Unit test runs.
  yield

  # Teardown.
  clear_embedding_registry()


def embed(examples: Iterable[RichData]) -> np.ndarray:
  """Embed the examples, use a hashmap to the vector for simplicity."""
  return np.array([STR_EMBEDDINGS[cast(str, example)] for example in examples])


def _make_indexer(embedding_indexer_cls: Type[EmbeddingIndexer],
                  tmp_path: pathlib.Path) -> EmbeddingIndexer:
  if embedding_indexer_cls == EmbeddingIndexerDisk:
    return EmbeddingIndexerDisk(tmp_path)
  raise ValueError('Cant create embedding indexer class ', embedding_indexer_cls)


class EmbeddingIndexerSuite:

  @pytest.mark.parametrize('indexer_cls', ALL_INDEXERS)
  def test_get_full_index(self, tmp_path: pathlib.Path, mocker: MockerFixture,
                          indexer_cls: Type[EmbeddingIndexer]) -> None:
    embed_mock = mocker.spy(sys.modules[__name__], embed.__name__)

    indexer = _make_indexer(indexer_cls, tmp_path)

    indexer.compute_embedding_index('test_column',
                                    TEST_EMBEDDING_NAME,
                                    keys=[key for key, _, _ in EMBEDDINGS],
                                    data=[text for _, text, _ in EMBEDDINGS])

    # Embed should only be called once.
    assert embed_mock.call_count == 1

    index = indexer.get_embedding_index('test_column', TEST_EMBEDDING_NAME)

    np.testing.assert_array_equal(index.embeddings,
                                  np.array([embedding for _, _, embedding in EMBEDDINGS]))

    # Embed should not be called again.
    assert embed_mock.call_count == 1

  @pytest.mark.parametrize('indexer_cls', ALL_INDEXERS)
  def test_get_partial_index(self, tmp_path: pathlib.Path, mocker: MockerFixture,
                             indexer_cls: Type[EmbeddingIndexer]) -> None:
    embed_mock = mocker.spy(sys.modules[__name__], embed.__name__)

    indexer = _make_indexer(indexer_cls, tmp_path)

    indexer.compute_embedding_index('test_column',
                                    TEST_EMBEDDING_NAME,
                                    keys=[key for key, _, _ in EMBEDDINGS],
                                    data=[text for _, text, _ in EMBEDDINGS])

    # Embed should only be called once.
    assert embed_mock.call_count == 1

    index = indexer.get_embedding_index(
        'test_column',
        TEST_EMBEDDING_NAME,
        # Keys are partial.
        keys=[b'1', b'2'])

    np.testing.assert_array_equal(
        index.embeddings,
        # Results should be partial.
        np.array([KEY_EMBEDDINGS[b'1'], KEY_EMBEDDINGS[b'2']]))

    # Embed should not be called again.
    assert embed_mock.call_count == 1
