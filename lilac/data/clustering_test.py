"""Unit tests for dataset.cluster()."""
import re
from typing import ClassVar, Iterable, Iterator

import numpy as np
import pytest
from pytest_mock import MockerFixture

from ..embeddings.jina import JinaV2Small
from ..formats import ShareGPT
from ..schema import ClusterInfo, Item, chunk_embedding, field, schema
from ..signal import TextSignal, clear_signal_registry, register_signal
from ..source import clear_source_registry, register_source
from . import clustering
from .clustering import (
  CATEGORY_ID,
  CATEGORY_MEMBERSHIP_PROB,
  CATEGORY_TITLE,
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


def _mock_jina(mocker: MockerFixture) -> None:
  def compute(docs: list[str]) -> list[Item]:
    result = []
    for doc in docs:
      if 'summar' in doc or 'hello' in doc or 'greeting' in doc:
        result.append([chunk_embedding(0, len(doc), np.array([1, 1, 1]))])
      elif 'simpl' in doc or 'whats' in doc or 'time' in doc:
        result.append([chunk_embedding(0, len(doc), np.array([0, 0, 0]))])
      else:
        result.append([chunk_embedding(0, len(doc), np.array([0.5, 0.5, 0.5]))])
    return result

  mocker.patch.object(JinaV2Small, 'compute', side_effect=compute)
  mocker.patch.object(JinaV2Small, 'setup', return_value=None)


def test_simple_clusters(make_test_data: TestDataMaker, mocker: MockerFixture) -> None:
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

  mocker.patch.object(clustering, 'MIN_CLUSTER_SIZE_CATEGORY', 2)
  _mock_jina(mocker)

  dataset.cluster(
    'text', min_cluster_size=2, topic_fn=topic_fn, category_fn=lambda _: 'MockCategory'
  )

  rows = list(dataset.select_rows(['text', 'text__cluster'], combine_columns=True))
  assert rows == [
    {
      'text': 'Can you summarize this article',
      'text__cluster': {
        'cluster_id': 0,
        'cluster_membership_prob': 1.0,
        'cluster_title': 'summarization',
        'category_id': 0,
        'category_membership_prob': 1.0,
        'category_title': 'MockCategory',
      },
    },
    {
      'text': 'Can you rewrite this in a simpler way',
      'text__cluster': {
        'cluster_id': 1,
        'cluster_membership_prob': 1.0,
        'cluster_title': 'simplification',
        'category_id': 1,
        'category_membership_prob': 1.0,
        'category_title': 'MockCategory',
      },
    },
    {
      'text': 'Can you provide a short summary of the following text',
      'text__cluster': {
        'cluster_id': 0,
        'cluster_membership_prob': 1.0,
        'cluster_title': 'summarization',
        'category_id': 0,
        'category_membership_prob': 1.0,
        'category_title': 'MockCategory',
      },
    },
    {
      'text': 'Can you simplify this text',
      'text__cluster': {
        'cluster_id': 1,
        'cluster_membership_prob': 1.0,
        'cluster_title': 'simplification',
        'category_id': 1,
        'category_membership_prob': 1.0,
        'category_title': 'MockCategory',
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
        'category_id': 0,
        'category_membership_prob': 1.0,
        'category_title': 'MockCategory',
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
        'category_id': 0,
        'category_membership_prob': 1.0,
        'category_title': 'MockCategory',
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
            CATEGORY_ID: field('int32', categorical=True),
            CATEGORY_MEMBERSHIP_PROB: 'float32',
            CATEGORY_TITLE: 'string',
          },
          cluster=ClusterInfo(min_cluster_size=2, use_garden=False, input_path=('text',)),
        ),
      }
    ),
    num_items=4,
    source=TestSource(),
  )


def test_nested_clusters(make_test_data: TestDataMaker, mocker: MockerFixture) -> None:
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
  mocker.patch.object(clustering, 'MIN_CLUSTER_SIZE_CATEGORY', 2)
  dataset = make_test_data([{'texts': t} for t in texts])

  def topic_fn(docs: list[tuple[str, float]]) -> str:
    if 'summar' in docs[0][0]:
      return 'summarization'
    elif 'simpl' in docs[0][0]:
      return 'simplification'
    return 'other'

  _mock_jina(mocker)

  dataset.cluster(
    'texts.*.text', min_cluster_size=2, topic_fn=topic_fn, category_fn=lambda _: 'MockCategory'
  )

  rows = list(dataset.select_rows(['texts_text__cluster'], combine_columns=True))
  assert rows == [
    {
      'texts_text__cluster': {
        'cluster_id': 0,
        'cluster_membership_prob': 1.0,
        'cluster_title': 'summarization',
        'category_id': 0,
        'category_membership_prob': 1.0,
        'category_title': 'MockCategory',
      },
    },
    {
      'texts_text__cluster': {
        'cluster_id': 1,
        'cluster_membership_prob': 1.0,
        'cluster_title': 'simplification',
        'category_id': 1,
        'category_membership_prob': 1.0,
        'category_title': 'MockCategory',
      },
    },
    {
      'texts_text__cluster': {
        'cluster_id': 0,
        'cluster_membership_prob': 1.0,
        'cluster_title': 'summarization',
        'category_id': 0,
        'category_membership_prob': 1.0,
        'category_title': 'MockCategory',
      },
    },
    {
      'texts_text__cluster': {
        'cluster_id': 1,
        'cluster_membership_prob': 1.0,
        'cluster_title': 'simplification',
        'category_id': 1,
        'category_membership_prob': 1.0,
        'category_title': 'MockCategory',
      },
    },
  ]


def test_path_ending_with_repeated(make_test_data: TestDataMaker, mocker: MockerFixture) -> None:
  texts: list[list[str]] = [['hello', 'teacher'], ['professor'], ['hi']]
  dataset = make_test_data([{'texts': t} for t in texts])

  def topic_fn(docs: list[tuple[str, float]]) -> str:
    if 'hello' in docs[0][0]:
      return 'a_cluster'
    elif 'teacher' in docs[0][0]:
      return 'b_cluster'
    return 'other'

  mocker.patch.object(clustering, 'MIN_CLUSTER_SIZE_CATEGORY', 2)
  _mock_jina(mocker)
  dataset.cluster(
    'texts.*', min_cluster_size=2, topic_fn=topic_fn, category_fn=lambda _: 'MockCategory'
  )
  rows = list(dataset.select_rows(combine_columns=True))
  assert rows == [
    {
      'texts': ['hello', 'teacher'],
      'texts__cluster': {
        'cluster_id': -1,
        'cluster_membership_prob': 0.0,
        'cluster_title': None,
        'category_id': -1,
        'category_membership_prob': 0.0,
        'category_title': None,
      },
    },
    {
      'texts': ['professor'],
      'texts__cluster': {
        'cluster_id': -1,
        'cluster_membership_prob': 0.0,
        'cluster_title': None,
        'category_id': -1,
        'category_membership_prob': 0.0,
        'category_title': None,
      },
    },
    {
      'texts': ['hi'],
      'texts__cluster': {
        'cluster_id': -1,
        'cluster_membership_prob': 0.0,
        'cluster_title': None,
        'category_id': -1,
        'category_membership_prob': 0.0,
        'category_title': None,
      },
    },
  ]


def test_clusters_with_fn(make_test_data: TestDataMaker, mocker: MockerFixture) -> None:
  texts: list[list[str]] = [
    ['Can you summarize this article'],
    ['Can you rewrite this in a simpler way'],
    ['Can you provide a short summary of the following text'],
    ['Can you simplify this text'],
  ]
  dataset = make_test_data([{'texts': t} for t in texts])
  mocker.patch.object(clustering, 'MIN_CLUSTER_SIZE_CATEGORY', 2)

  def topic_fn(docs: list[tuple[str, float]]) -> str:
    if 'summar' in docs[0][0]:
      return 'summarization'
    elif 'simpl' in docs[0][0]:
      return 'simplification'
    return 'other'

  with pytest.raises(
    ValueError,
    match=re.escape(
      '`output_path` must be provided to `Dataset.cluster()` when `input` is a '
      'user-provided method.'
    ),
  ):
    dataset.cluster(lambda row: '\n'.join(row['texts']), min_cluster_size=2, topic_fn=topic_fn)

  _mock_jina(mocker)
  dataset.cluster(
    lambda row: '\n'.join(row['texts']),
    output_path='cluster',
    min_cluster_size=2,
    topic_fn=topic_fn,
    category_fn=lambda _: 'MockCategory',
  )
  rows = list(dataset.select_rows(combine_columns=True))
  assert rows == [
    {
      'texts': ['Can you summarize this article'],
      'cluster': {
        'cluster_id': 0,
        'cluster_membership_prob': 1.0,
        'cluster_title': 'summarization',
        'category_id': 0,
        'category_membership_prob': 1.0,
        'category_title': 'MockCategory',
      },
    },
    {
      'texts': ['Can you rewrite this in a simpler way'],
      'cluster': {
        'cluster_id': 1,
        'cluster_membership_prob': 1.0,
        'cluster_title': 'simplification',
        'category_id': 1,
        'category_membership_prob': 1.0,
        'category_title': 'MockCategory',
      },
    },
    {
      'texts': ['Can you provide a short summary of the following text'],
      'cluster': {
        'cluster_id': 0,
        'cluster_membership_prob': 1.0,
        'cluster_title': 'summarization',
        'category_id': 0,
        'category_membership_prob': 1.0,
        'category_title': 'MockCategory',
      },
    },
    {
      'texts': ['Can you simplify this text'],
      'cluster': {
        'cluster_id': 1,
        'cluster_membership_prob': 1.0,
        'cluster_title': 'simplification',
        'category_id': 1,
        'category_membership_prob': 1.0,
        'category_title': 'MockCategory',
      },
    },
  ]


def test_clusters_with_fn_output_is_under_a_dict(
  make_test_data: TestDataMaker, mocker: MockerFixture
) -> None:
  texts: list[list[str]] = [
    ['Can you summarize this article'],
    ['Can you rewrite this in a simpler way'],
    ['Can you provide a short summary of the following text'],
    ['Can you simplify this text'],
  ]
  dataset = make_test_data([{'texts': t, 'info': {'dummy': True}} for t in texts])
  mocker.patch.object(clustering, 'MIN_CLUSTER_SIZE_CATEGORY', 2)

  def topic_fn(docs: list[tuple[str, float]]) -> str:
    if 'summar' in docs[0][0]:
      return 'summarization'
    elif 'simpl' in docs[0][0]:
      return 'simplification'
    return 'other'

  _mock_jina(mocker)
  dataset.cluster(
    lambda row: '\n'.join(row['texts']),
    output_path=('info', 'cluster'),
    min_cluster_size=2,
    topic_fn=topic_fn,
    category_fn=lambda _: 'MockCategory',
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
          'category_id': 0,
          'category_membership_prob': 1.0,
          'category_title': 'MockCategory',
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
          'category_id': 1,
          'category_membership_prob': 1.0,
          'category_title': 'MockCategory',
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
          'category_id': 0,
          'category_membership_prob': 1.0,
          'category_title': 'MockCategory',
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
          'category_id': 1,
          'category_membership_prob': 1.0,
          'category_title': 'MockCategory',
        },
      },
    },
  ]


def test_clusters_sharegpt(make_test_data: TestDataMaker, mocker: MockerFixture) -> None:
  texts: list[Item] = [
    {
      'conversations': [
        {'from': 'human', 'value': 'hello'},
        {'from': 'gpt', 'value': 'i am a language model'},
      ]
    },
    {
      'conversations': [
        {'from': 'human', 'value': 'whats the time'},
        {'from': 'gpt', 'value': '1030'},
      ]
    },
    {
      'conversations': [
        {'from': 'human', 'value': 'hello how are you'},
        {'from': 'gpt', 'value': 'pretty good today'},
      ]
    },
    {
      'conversations': [
        {'from': 'human', 'value': 'whats the hour'},
        {'from': 'gpt', 'value': '10 is the hour'},
      ]
    },
  ]
  dataset = make_test_data(texts)

  topic_fn_calls: list[list[tuple[str, float]]] = []

  def topic_fn(docs: list[tuple[str, float]]) -> str:
    topic_fn_calls.append(docs)
    if 'hello' in docs[0][0]:
      return 'greeting'
    elif 'time' in docs[0][0] or 'hour' in docs[0][0]:
      return 'time'
    return 'other'

  mocker.patch.object(clustering, 'MIN_CLUSTER_SIZE_CATEGORY', 2)
  _mock_jina(mocker)
  dataset.cluster(
    ShareGPT.human,
    output_path='cluster',
    min_cluster_size=2,
    topic_fn=topic_fn,
    category_fn=lambda _: 'MockCategory',
  )

  # Sort because topics are shuffled.
  for topic_fn_call in topic_fn_calls:
    topic_fn_call.sort()

  # Make sure the topic function is only called for the human text.
  assert topic_fn_calls == [
    [('hello', 1.0), ('hello how are you', 1.0)],
    [('whats the hour', 1.0), ('whats the time', 1.0)],
  ]

  rows = list(dataset.select_rows(combine_columns=True))
  assert rows == [
    {
      'conversations': [
        {'from': 'human', 'value': 'hello'},
        {'from': 'gpt', 'value': 'i am a language model'},
      ],
      'cluster': {
        'cluster_id': 0,
        'cluster_membership_prob': 1.0,
        'cluster_title': 'greeting',
        'category_id': 0,
        'category_membership_prob': 1.0,
        'category_title': 'MockCategory',
      },
    },
    {
      'conversations': [
        {'from': 'human', 'value': 'whats the time'},
        {'from': 'gpt', 'value': '1030'},
      ],
      'cluster': {
        'cluster_id': 1,
        'cluster_membership_prob': 1.0,
        'cluster_title': 'time',
        'category_id': 1,
        'category_membership_prob': 1.0,
        'category_title': 'MockCategory',
      },
    },
    {
      'conversations': [
        {'from': 'human', 'value': 'hello how are you'},
        {'from': 'gpt', 'value': 'pretty good today'},
      ],
      'cluster': {
        'cluster_id': 0,
        'cluster_membership_prob': 1.0,
        'cluster_title': 'greeting',
        'category_id': 0,
        'category_membership_prob': 1.0,
        'category_title': 'MockCategory',
      },
    },
    {
      'conversations': [
        {'from': 'human', 'value': 'whats the hour'},
        {'from': 'gpt', 'value': '10 is the hour'},
      ],
      'cluster': {
        'cluster_id': 1,
        'cluster_membership_prob': 1.0,
        'cluster_title': 'time',
        'category_id': 1,
        'category_membership_prob': 1.0,
        'category_title': 'MockCategory',
      },
    },
  ]


def test_clusters_on_enriched_text(make_test_data: TestDataMaker, mocker: MockerFixture) -> None:
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
  mocker.patch.object(clustering, 'MIN_CLUSTER_SIZE_CATEGORY', 2)
  _mock_jina(mocker)

  dataset.cluster(
    'text', min_cluster_size=2, topic_fn=topic_fn, category_fn=lambda _: 'MockCategory'
  )

  rows = list(dataset.select_rows(['text', 'text__cluster'], combine_columns=True))
  assert rows == [
    {
      'text': enriched_item('Can you summarize this article', {'test_signal': 30}),
      'text__cluster': {
        'cluster_id': 0,
        'cluster_membership_prob': 1.0,
        'cluster_title': 'summarization',
        'category_id': 0,
        'category_membership_prob': 1.0,
        'category_title': 'MockCategory',
      },
    },
    {
      'text': enriched_item('Can you rewrite this in a simpler way', {'test_signal': 37}),
      'text__cluster': {
        'cluster_id': 1,
        'cluster_membership_prob': 1.0,
        'cluster_title': 'simplification',
        'category_id': 1,
        'category_membership_prob': 1.0,
        'category_title': 'MockCategory',
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
        'category_id': 0,
        'category_membership_prob': 1.0,
        'category_title': 'MockCategory',
      },
    },
    {
      'text': enriched_item('Can you simplify this text', {'test_signal': 26}),
      'text__cluster': {
        'cluster_id': 1,
        'cluster_membership_prob': 1.0,
        'cluster_title': 'simplification',
        'category_id': 1,
        'category_membership_prob': 1.0,
        'category_title': 'MockCategory',
      },
    },
  ]
