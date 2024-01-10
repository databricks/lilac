"""Unit tests for dataset.cluster()."""
from typing import ClassVar, Iterable, Iterator

import pytest

from ..embeddings.jina import JinaV2Small
from ..schema import ClusterInfo, field, schema
from ..signal import TextSignal, clear_signal_registry, register_signal
from ..source import clear_source_registry, register_source
from .clustering import (
  CATEGORY_MEMBERSHIP_PROB,
  CATEGORY_TITLE,
  CATEROGY_ID,
  CLUSTER_ID,
  CLUSTER_MEMBERSHIP_PROB,
  CLUSTER_TITLE,
)
from .dataset import DatasetManifest, MetadataSearch
from .dataset_test_utils import (
  TEST_DATASET_NAME,
  TEST_NAMESPACE,
  TestDataMaker,
  TestSource,
  enriched_item,
)


class TestSignal(TextSignal):
  name: ClassVar[str] = 'test_signal'

  def compute(self, data: Iterator[str]) -> Iterator[int]:
    for text_content in data:
      yield len(text_content)


@pytest.fixture(scope='module', autouse=True)
def setup_teardown() -> Iterable[None]:
  # Setup.
  clear_signal_registry()
  clear_source_registry()
  register_source(TestSource)
  register_signal(JinaV2Small)
  register_signal(TestSignal)

  # Unit test runs.
  yield

  # Teardown.
  clear_signal_registry()
  clear_source_registry()


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

  assert dataset.manifest() == DatasetManifest(
    namespace=TEST_NAMESPACE,
    dataset_name=TEST_DATASET_NAME,
    data_schema=schema(
      {
        'text': 'string',
        'text__cluster': field(
          fields={
            CLUSTER_ID: field('int32', categorical=True),
            CLUSTER_MEMBERSHIP_PROB: 'float32',
            CLUSTER_TITLE: 'string',
            CATEROGY_ID: field('int32', categorical=True),
            CATEGORY_MEMBERSHIP_PROB: 'float32',
            CATEGORY_TITLE: 'string',
          },
          cluster=ClusterInfo(min_cluster_size=2, remote=False, input_path=('text',)),
        ),
      }
    ),
    num_items=4,
    source=TestSource(),
  )


def test_nested_clusters(make_test_data: TestDataMaker) -> None:
  texts: list[list[dict[str, str]]] = [
    [  # Cluster 1
      {'text': 'Can you summarize this article'},
      {'text': 'Can you provide a short summary of the following text'},
    ],
    [  # Cluster 2
      {'text': 'Can you rewrite this in a simpler way'},
      {'text': 'Can you simplify this text'},
    ],
    [  # Cluster 1
      {'text': 'Can you give a summary of the article'},
      {'text': 'Write a short overview of the following text'},
    ],
    [  # Cluster 2
      {'text': 'Can you write a simpler version'},
      {'text': 'Give me simplified version of this text'},
    ],
  ]
  dataset = make_test_data([{'texts': t} for t in texts])

  def topic_fn(docs: list[tuple[str, float]]) -> str:
    if 'summar' in docs[0][0]:
      return 'summarization'
    elif 'simpl' in docs[0][0]:
      return 'simplification'
    return 'other'

  dataset.cluster('texts.*.text', min_cluster_size=2, topic_fn=topic_fn)

  rows = list(dataset.select_rows(['texts_text__cluster'], combine_columns=True))
  assert rows == [
    {
      'texts_text__cluster': {
        'cluster_id': 0,
        'cluster_membership_prob': 1.0,
        'cluster_title': 'summarization',
        'category_id': -1,
        'category_membership_prob': None,
        'category_title': None,
      },
    },
    {
      'texts_text__cluster': {
        'cluster_id': 1,
        'cluster_membership_prob': 1.0,
        'cluster_title': 'simplification',
        'category_id': -1,
        'category_membership_prob': None,
        'category_title': None,
      },
    },
    {
      'texts_text__cluster': {
        'cluster_id': 0,
        'cluster_membership_prob': 1.0,
        'cluster_title': 'summarization',
        'category_id': -1,
        'category_membership_prob': None,
        'category_title': None,
      },
    },
    {
      'texts_text__cluster': {
        'cluster_id': 1,
        'cluster_membership_prob': 1.0,
        'cluster_title': 'simplification',
        'category_id': -1,
        'category_membership_prob': None,
        'category_title': None,
      },
    },
  ]


def test_path_ending_with_repeated(make_test_data: TestDataMaker) -> None:
  texts: list[list[str]] = [['hello', 'teacher'], ['professor'], ['hi']]
  dataset = make_test_data([{'texts': t} for t in texts])

  def topic_fn(docs: list[tuple[str, float]]) -> str:
    if 'hello' in docs[0][0]:
      return 'a_cluster'
    elif 'teacher' in docs[0][0]:
      return 'b_cluster'
    return 'other'

  dataset.cluster('texts.*', min_cluster_size=2, topic_fn=topic_fn)
  rows = list(dataset.select_rows(combine_columns=True))
  assert rows == [
    {
      'texts': ['hello', 'teacher'],
      'texts__cluster': {
        'cluster_id': -1,
        'cluster_membership_prob': None,
        'cluster_title': None,
        'category_id': -1,
        'category_membership_prob': None,
        'category_title': None,
      },
    },
    {
      'texts': ['professor'],
      'texts__cluster': {
        'cluster_id': -1,
        'cluster_membership_prob': None,
        'cluster_title': None,
        'category_id': -1,
        'category_membership_prob': None,
        'category_title': None,
      },
    },
    {
      'texts': ['hi'],
      'texts__cluster': {
        'cluster_id': -1,
        'cluster_membership_prob': None,
        'cluster_title': None,
        'category_id': -1,
        'category_membership_prob': None,
        'category_title': None,
      },
    },
  ]


def test_clusters_with_fn(make_test_data: TestDataMaker) -> None:
  texts: list[list[str]] = [
    ['Can you summarize this article'],
    ['Can you rewrite this in a simpler way'],
    ['Can you provide a short summary of the following text'],
    ['Can you simplify this text'],
  ]
  dataset = make_test_data([{'texts': t} for t in texts])

  def topic_fn(docs: list[tuple[str, float]]) -> str:
    if 'summar' in docs[0][0]:
      return 'summarization'
    elif 'simpl' in docs[0][0]:
      return 'simplification'
    return 'other'

  with pytest.raises(ValueError, match='output_path must be provided if input is a function'):
    dataset.cluster(lambda row: '\n'.join(row['texts']), min_cluster_size=2, topic_fn=topic_fn)

  dataset.cluster(
    lambda row: '\n'.join(row['texts']),
    output_path='cluster',
    min_cluster_size=2,
    topic_fn=topic_fn,
  )
  rows = list(dataset.select_rows(combine_columns=True))
  assert rows == [
    {
      'texts': ['Can you summarize this article'],
      'cluster': {
        'cluster_id': 0,
        'cluster_membership_prob': 1.0,
        'cluster_title': 'summarization',
        'category_id': -1,
        'category_membership_prob': None,
        'category_title': None,
      },
    },
    {
      'texts': ['Can you rewrite this in a simpler way'],
      'cluster': {
        'cluster_id': 1,
        'cluster_membership_prob': 1.0,
        'cluster_title': 'simplification',
        'category_id': -1,
        'category_membership_prob': None,
        'category_title': None,
      },
    },
    {
      'texts': ['Can you provide a short summary of the following text'],
      'cluster': {
        'cluster_id': 0,
        'cluster_membership_prob': 1.0,
        'cluster_title': 'summarization',
        'category_id': -1,
        'category_membership_prob': None,
        'category_title': None,
      },
    },
    {
      'texts': ['Can you simplify this text'],
      'cluster': {
        'cluster_id': 1,
        'cluster_membership_prob': 1.0,
        'cluster_title': 'simplification',
        'category_id': -1,
        'category_membership_prob': None,
        'category_title': None,
      },
    },
  ]


def test_clusters_with_fn_output_is_under_a_dict(make_test_data: TestDataMaker) -> None:
  texts: list[list[str]] = [
    ['Can you summarize this article'],
    ['Can you rewrite this in a simpler way'],
    ['Can you provide a short summary of the following text'],
    ['Can you simplify this text'],
  ]
  dataset = make_test_data([{'texts': t, 'info': {'dummy': True}} for t in texts])

  def topic_fn(docs: list[tuple[str, float]]) -> str:
    if 'summar' in docs[0][0]:
      return 'summarization'
    elif 'simpl' in docs[0][0]:
      return 'simplification'
    return 'other'

  dataset.cluster(
    lambda row: '\n'.join(row['texts']),
    output_path=('info', 'cluster'),
    min_cluster_size=2,
    topic_fn=topic_fn,
  )
  rows = list(dataset.select_rows(combine_columns=True))
  assert rows == [
    {
      'texts': ['Can you summarize this article'],
      'info': {
        'dummy': True,
        'cluster': {
          'cluster_id': 0,
          'cluster_membership_prob': 1.0,
          'cluster_title': 'summarization',
          'category_id': -1,
          'category_membership_prob': None,
          'category_title': None,
        },
      },
    },
    {
      'texts': ['Can you rewrite this in a simpler way'],
      'info': {
        'dummy': True,
        'cluster': {
          'cluster_id': 1,
          'cluster_membership_prob': 1.0,
          'cluster_title': 'simplification',
          'category_id': -1,
          'category_membership_prob': None,
          'category_title': None,
        },
      },
    },
    {
      'texts': ['Can you provide a short summary of the following text'],
      'info': {
        'dummy': True,
        'cluster': {
          'cluster_id': 0,
          'cluster_membership_prob': 1.0,
          'cluster_title': 'summarization',
          'category_id': -1,
          'category_membership_prob': None,
          'category_title': None,
        },
      },
    },
    {
      'texts': ['Can you simplify this text'],
      'info': {
        'dummy': True,
        'cluster': {
          'cluster_id': 1,
          'cluster_membership_prob': 1.0,
          'cluster_title': 'simplification',
          'category_id': -1,
          'category_membership_prob': None,
          'category_title': None,
        },
      },
    },
  ]


def test_clusters_on_enriched_text(make_test_data: TestDataMaker) -> None:
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

  signal = TestSignal()
  dataset.compute_signal(signal, 'text')
  dataset.cluster('text', min_cluster_size=2, topic_fn=topic_fn)

  rows = list(dataset.select_rows(['text', 'text__cluster'], combine_columns=True))
  assert rows == [
    {
      'text': enriched_item('Can you summarize this article', {'test_signal': 30}),
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
      'text': enriched_item('Can you rewrite this in a simpler way', {'test_signal': 37}),
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
      'text': enriched_item(
        'Can you provide a short summary of the following text', {'test_signal': 53}
      ),
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
      'text': enriched_item('Can you simplify this text', {'test_signal': 26}),
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
