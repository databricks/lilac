"""Unit tests for dataset.cluster()."""
import re
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


def test_simple_clusters(make_test_data: TestDataMaker) -> None:
  texts: list[str] = [
    'Can you summarize this article',
    'Can you rewrite this in a simpler way',
    'Can you provide a short summary of the following text',
    'Can you simplify this text',
  ]
  dataset = make_test_data([{'text': t} for t in texts])

  def topic_fn(docs: list[tuple[str, float]]) -> str:
    if 'summar' in docs[0][0]:
      return 'summarization'
    elif 'simpl' in docs[0][0]:
      return 'simplification'
    return 'other'

  dataset.cluster('text', min_cluster_size=2, topic_fn=topic_fn)

  rows = list(dataset.select_rows(['text', 'text_cluster'], combine_columns=True))
  assert rows == [
    {
      'text': 'Can you summarize this article',
      'text_cluster': {'cluster_id': 0, 'membership_prob': 1.0, 'topic': 'summarization'},
    },
    {
      'text': 'Can you rewrite this in a simpler way',
      'text_cluster': {'cluster_id': 1, 'membership_prob': 1.0, 'topic': 'simplification'},
    },
    {
      'text': 'Can you provide a short summary of the following text',
      'text_cluster': {'cluster_id': 0, 'membership_prob': 1.0, 'topic': 'summarization'},
    },
    {
      'text': 'Can you simplify this text',
      'text_cluster': {'cluster_id': 1, 'membership_prob': 1.0, 'topic': 'simplification'},
    },
  ]


def test_nested_clusters(make_test_data: TestDataMaker) -> None:
  texts: list[list[dict[str, str]]] = [
    [{'text': 'Can you summarize this article'}, {'text': 'Can you rewrite this in a simpler way'}],
    [{'text': 'Can you provide a short summary of the following text'}],
    [{'text': 'Can you simplify this text'}, {'text': '1224123531451345'}],
  ]
  dataset = make_test_data([{'texts': t} for t in texts])

  def topic_fn(docs: list[tuple[str, float]]) -> str:
    if 'summar' in docs[0][0]:
      return 'summarization'
    elif 'simpl' in docs[0][0]:
      return 'simplification'
    return 'other'

  dataset.cluster('texts.*.text', min_cluster_size=2, topic_fn=topic_fn)

  rows = list(dataset.select_rows(['texts'], combine_columns=True))
  assert rows == [
    {
      'texts': [
        {
          'text': 'Can you summarize this article',
          'text_cluster': {'cluster_id': 0, 'membership_prob': 1.0, 'topic': 'summarization'},
        },
        {
          'text': 'Can you rewrite this in a simpler way',
          'text_cluster': {'cluster_id': 1, 'membership_prob': 1.0, 'topic': 'simplification'},
        },
      ]
    },
    {
      'texts': [
        {
          'text': 'Can you provide a short summary of the following text',
          'text_cluster': {'cluster_id': 0, 'membership_prob': 1.0, 'topic': 'summarization'},
        }
      ],
    },
    {
      'texts': [
        {
          'text': 'Can you simplify this text',
          'text_cluster': {'cluster_id': 1, 'membership_prob': 1.0, 'topic': 'simplification'},
        },
        {
          'text': '1224123531451345',
          'text_cluster': {'cluster_id': -1, 'membership_prob': None, 'topic': None},
        },
      ],
    },
  ]


def test_path_ending_with_repeated_errors(make_test_data: TestDataMaker) -> None:
  texts: list[list[str]] = [['a', 'b'], ['c'], ['d']]
  dataset = make_test_data([{'texts': t} for t in texts])

  with pytest.raises(
    ValueError, match=re.escape("Path ('texts', '*') must end with a field name.")
  ):
    dataset.cluster('texts.*')
