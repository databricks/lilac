"""Unit tests for dataset.cluster()."""
import re
from typing import Iterable

import pytest

from ..embeddings.jina import JinaV2Small
from ..signal import clear_signal_registry, register_signal
from .dataset import MetadataSearch
from .dataset_test_utils import TestDataMaker, enriched_item


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

  rows = list(dataset.select_rows(['text', 'text__cluster'], combine_columns=True))
  assert rows == [
    {
      'text': 'Can you summarize this article',
      'text__cluster': {
        'cluster_id': 0,
        'cluster_membership_prob': 1.0,
        'cluster_title': 'summarization',
        'category_id': -1,
        'category_membership_prob': None,
        'category_title': None,
      },
    },
    {
      'text': 'Can you rewrite this in a simpler way',
      'text__cluster': {
        'cluster_id': 1,
        'cluster_membership_prob': 1.0,
        'cluster_title': 'simplification',
        'category_id': -1,
        'category_membership_prob': None,
        'category_title': None,
      },
    },
    {
      'text': 'Can you provide a short summary of the following text',
      'text__cluster': {
        'cluster_id': 0,
        'cluster_membership_prob': 1.0,
        'cluster_title': 'summarization',
        'category_id': -1,
        'category_membership_prob': None,
        'category_title': None,
      },
    },
    {
      'text': 'Can you simplify this text',
      'text__cluster': {
        'cluster_id': 1,
        'cluster_membership_prob': 1.0,
        'cluster_title': 'simplification',
        'category_id': -1,
        'category_membership_prob': None,
        'category_title': None,
      },
    },
  ]

  rows = list(
    dataset.select_rows(
      ['text__cluster'],
      searches=[
        MetadataSearch(path='text__cluster.cluster_title', op='equals', value='summarization')
      ],
      combine_columns=True,
    )
  )
  assert rows == [
    {
      'text__cluster': {
        'cluster_id': 0,
        'cluster_membership_prob': 1.0,
        'cluster_title': enriched_item(
          'summarization',
          {
            'metadata_search(op=equals,value=summarization)': True,
          },
        ),
        'category_id': -1,
        'category_membership_prob': None,
        'category_title': None,
      },
    },
    {
      'text__cluster': {
        'cluster_id': 0,
        'cluster_membership_prob': 1.0,
        'cluster_title': enriched_item(
          'summarization',
          {
            'metadata_search(op=equals,value=summarization)': True,
          },
        ),
        'category_id': -1,
        'category_membership_prob': None,
        'category_title': None,
      },
    },
  ]

  rows = list(
    dataset.select_rows(
      ['text__cluster'],
      searches=[
        MetadataSearch(path='text__cluster.category_title', op='equals', value='non_existent')
      ],
      combine_columns=True,
    )
  )
  assert rows == []


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
          'text__cluster': {
            'cluster_id': 0,
            'cluster_membership_prob': 1.0,
            'cluster_title': 'summarization',
            'category_id': -1,
            'category_membership_prob': None,
            'category_title': None,
          },
        },
        {
          'text': 'Can you rewrite this in a simpler way',
          'text__cluster': {
            'cluster_id': 1,
            'cluster_membership_prob': 1.0,
            'cluster_title': 'simplification',
            'category_id': -1,
            'category_membership_prob': None,
            'category_title': None,
          },
        },
      ]
    },
    {
      'texts': [
        {
          'text': 'Can you provide a short summary of the following text',
          'text__cluster': {
            'cluster_id': 0,
            'cluster_membership_prob': 1.0,
            'cluster_title': 'summarization',
            'category_id': -1,
            'category_membership_prob': None,
            'category_title': None,
          },
        }
      ],
    },
    {
      'texts': [
        {
          'text': 'Can you simplify this text',
          'text__cluster': {
            'cluster_id': 1,
            'cluster_membership_prob': 1.0,
            'cluster_title': 'simplification',
            'category_id': -1,
            'category_membership_prob': None,
            'category_title': None,
          },
        },
        {
          'text': '1224123531451345',
          'text__cluster': {
            'cluster_id': -1,
            'cluster_membership_prob': None,
            'cluster_title': None,
            'category_id': None,
            'category_membership_prob': None,
            'category_title': None,
          },
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
