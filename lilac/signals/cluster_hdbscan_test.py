"""Tests for the cluster signal."""

import os
import pathlib
from typing import ClassVar, Iterable, cast

import numpy as np
import pytest
from pytest_mock import MockerFixture
from typing_extensions import override

from ..data.dataset_test_utils import TestDataMaker, enriched_item
from ..schema import Item, RichData, lilac_embedding, lilac_span
from ..signal import TextEmbeddingSignal, clear_signal_registry, register_signal
from .cluster_hdbscan import ClusterHDBScan

TEST_ITEMS: list[Item] = [{'text': 'a'}, {'text': 'b'}, {'text': 'c'}]

EMBEDDINGS: dict[str, list[float]] = {
  'a': [1.0, 0.0, 0.0],
  'b': [0.0, 1.0, 0.0],
  'c': [1.0, 0.1, 0.0],
  'd': [0.0, 0.9, 0.0],
}


@pytest.fixture(autouse=True)
def set_project_dir(tmp_path: pathlib.Path, mocker: MockerFixture) -> None:
  mocker.patch.dict(os.environ, {'LILAC_PROJECT_DIR': str(tmp_path)})


@pytest.fixture(scope='module', autouse=True)
def setup_teardown() -> Iterable[None]:
  # Setup.
  clear_signal_registry()
  register_signal(TestEmbedding)
  register_signal(ClusterHDBScan)
  # Unit test runs.
  yield
  # Teardown.
  clear_signal_registry()


class TestEmbedding(TextEmbeddingSignal):
  """A test embed function."""

  name: ClassVar[str] = 'test_embedding'

  @override
  def compute(self, data: Iterable[RichData]) -> Iterable[Item]:
    """Call the embedding function."""
    for example in data:
      yield [lilac_embedding(0, len(example), np.array(EMBEDDINGS[cast(str, example)]))]


def test_simple_data(make_test_data: TestDataMaker, mocker: MockerFixture) -> None:
  dataset = make_test_data([{'text': 'a'}, {'text': 'b'}, {'text': 'c'}, {'text': 'd'}])
  dataset.compute_embedding('test_embedding', 'text')

  signal = ClusterHDBScan(
    embedding='test_embedding', min_cluster_size=2, umap_n_components=2, umap_random_state=1337
  )
  dataset.compute_signal(signal, 'text')
  signal_key = signal.key(is_computed_signal=True)
  result = dataset.select_rows(combine_columns=True)
  expected_result = [
    {'text': enriched_item('a', {signal_key: [lilac_span(0, 1, {'cluster_id': 0})]})},
    {'text': enriched_item('b', {signal_key: [lilac_span(0, 1, {'cluster_id': 1})]})},
    {'text': enriched_item('c', {signal_key: [lilac_span(0, 1, {'cluster_id': 0})]})},
    {'text': enriched_item('d', {signal_key: [lilac_span(0, 1, {'cluster_id': 1})]})},
  ]
  assert list(result) == expected_result
