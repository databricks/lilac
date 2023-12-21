"""Unit tests for dataset.cluster()."""
from typing import Iterable

import pytest

from ..embeddings.jina import JinaV2Small
from ..signal import clear_signal_registry, register_signal
from .dataset_test_utils import TestDataMaker


@pytest.fixture(scope='module', autouse=True)
def setup_teardown() -> Iterable[None]:
  # Setup.
  clear_signal_registry()
  register_signal(JinaV2Small)

  # Unit test runs.
  yield

  # Teardown.
  clear_signal_registry()


def test_simple_clustering(make_test_data: TestDataMaker) -> None:
  texts: list[str] = [
    'Can you summarize this article',
    'Can you rewrite this in a simpler way',
    'Can you provide a short summary of the following text',
    'Can you simplify this text',
  ]
  dataset = make_test_data([{'text': t} for t in texts])
  dataset.compute_embedding('jina-v2-small', 'text')

  def topic_fn(docs: list[tuple[str, float]]) -> str:
    if 'summar' in docs[0][0]:
      return 'summarization'
    elif 'simpl' in docs[0][0]:
      return 'simplification'
    return 'other'

  dataset.cluster('text', 'jina-v2-small', min_cluster_size=2, topic_fn=topic_fn)

  rows = list(dataset.select_rows(['text.topic']))
  assert rows == [
    {'text.topic': 'summarization'},
    {'text.topic': 'simplification'},
    {'text.topic': 'summarization'},
    {'text.topic': 'simplification'},
  ]
