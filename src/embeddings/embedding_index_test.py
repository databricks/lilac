"""Tests for embedding indexers."""

import pathlib
from typing import Iterable, Type, cast

import numpy as np
import pytest
from pytest_mock import MockerFixture
from typing_extensions import override

from ..schema import EnrichmentType, PathTuple, RichData
from .embedding_index import EmbeddingIndexer, EmbeddingIndexerManifest, EmbeddingIndexInfo
from .embedding_index_disk import EmbeddingIndexerDisk
from .embedding_registry import Embedding, clear_embedding_registry, register_embedding

ALL_INDEXERS: list[Type[EmbeddingIndexer]] = [EmbeddingIndexerDisk]

TEST_EMBEDDING_NAME = 'test_embedding'

EMBEDDINGS: list[tuple[PathTuple, str, list[float]]] = [(('1',), 'hello', [1.0, 0.0, 0.0]),
                                                        (('2',), 'hello world', [0.9, 0.1, 0.0]),
                                                        (('3',), 'far', [0.0, 0.0, 1.0])]

STR_EMBEDDINGS: dict[str, list[float]] = {text: embedding for _, text, embedding in EMBEDDINGS}


class TestEmbedding(Embedding):
  """A test embed function."""
  name = TEST_EMBEDDING_NAME
  enrichment_type = EnrichmentType.TEXT

  @override
  def __call__(self, data: Iterable[RichData]) -> np.ndarray:
    """Call the embedding function."""
    return np.array([STR_EMBEDDINGS[cast(str, example)] for example in data])


@pytest.fixture(scope='module', autouse=True)
def setup_teardown() -> Iterable[None]:
  # Setup.
  register_embedding(TestEmbedding)

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
    embed_mock = mocker.spy(TestEmbedding, '__call__')

    indexer = _make_indexer(indexer_cls, tmp_path)

    embedding = TestEmbedding()
    indexer.compute_embedding_index(
        'test_column',
        embedding,
        keys=[key for key, _, _ in EMBEDDINGS],
        data=[text for _, text, _ in EMBEDDINGS])

    # Embed should only be called once.
    assert embed_mock.call_count == 1

    index = indexer.get_embedding_index('test_column', TestEmbedding())

    np.testing.assert_array_equal(index.embeddings,
                                  np.array([embedding for _, _, embedding in EMBEDDINGS]))

    # Embed should not be called again.
    assert embed_mock.call_count == 1

    assert indexer.manifest() == EmbeddingIndexerManifest(
        indexes=[EmbeddingIndexInfo(column=('test_column',), embedding=embedding)])
