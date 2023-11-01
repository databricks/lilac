"""Tests for dataset.select_rows(searches=[...])."""

from typing import ClassVar, Iterable, cast

import numpy as np
import pytest
from pytest import approx
from pytest_mock import MockerFixture
from typing_extensions import override

from ..concepts.concept import ExampleIn, LogisticEmbeddingModel
from ..concepts.db_concept import ConceptUpdate, DiskConceptDB
from ..db_manager import set_default_dataset_cls
from ..schema import ROWID, Item, RichData, SignalInputType, lilac_embedding, lilac_span
from ..signal import TextEmbeddingSignal, clear_signal_registry, register_signal
from ..signals.concept_scorer import ConceptSignal
from ..signals.semantic_similarity import SemanticSimilaritySignal
from ..signals.substring_search import SubstringSignal
from .dataset import ConceptSearch, Filter, KeywordSearch, SemanticSearch, SortOrder
from .dataset_duckdb import DatasetDuckDB
from .dataset_test_utils import TestDataMaker, enriched_item

TEST_DATA: list[Item] = [
  {'text': 'hello world', 'text2': 'again hello world'},
  {'text': 'looking for world in text', 'text2': 'again looking for world in text'},
  {'text': 'unrelated text', 'text2': 'again unrelated text'},
]

EMBEDDINGS: list[tuple[str, list[float]]] = [
  ('hello.', [1.0, 0.0, 0.0]),
  ('hello2.', [1.0, 1.0, 0.0]),
  ('hello world.', [1.0, 1.0, 1.0]),
  ('hello world2.', [2.0, 1.0, 1.0]),
  ('random negative 1', [0, 0, 0.3]),
  ('random negative 2', [0, 0, 0.4]),
  ('random negative 3', [0, 0.1, 0.5]),
  ('random negative 4', [0.1, 0, 0.4]),
]

STR_EMBEDDINGS: dict[str, list[float]] = {text: embedding for text, embedding in EMBEDDINGS}


@pytest.fixture(scope='module', autouse=True)
def setup_teardown() -> Iterable[None]:
  # Setup.
  set_default_dataset_cls(DatasetDuckDB)
  register_signal(TestEmbedding)

  # Unit test runs.
  yield

  # Teardown.
  clear_signal_registry()


def test_search_keyword(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data(TEST_DATA)

  query = 'world'
  result = dataset.select_rows(
    searches=[KeywordSearch(path='text', query=query)], combine_columns=True
  )

  expected_signal_udf = SubstringSignal(query=query)
  assert list(result) == [
    {
      'text': enriched_item('hello world', {expected_signal_udf.key(): [lilac_span(6, 11)]}),
      'text2': 'again hello world',
    },
    {
      'text': enriched_item(
        'looking for world in text', {expected_signal_udf.key(): [lilac_span(12, 17)]}
      ),
      'text2': 'again looking for world in text',
    },
  ]


def test_search_keyword_special_chars(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data([{'text': 'This is 100%'}, {'text': 'This has _underscore_'}])

  query = '100%'
  result = dataset.select_rows(
    searches=[KeywordSearch(path='text', query=query)], combine_columns=True
  )

  expected_signal_udf = SubstringSignal(query=query)
  assert list(result) == [
    {'text': enriched_item('This is 100%', {expected_signal_udf.key(): [lilac_span(8, 12)]})}
  ]

  query = '_underscore_'
  result = dataset.select_rows(
    searches=[KeywordSearch(path='text', query=query)], combine_columns=True
  )

  expected_signal_udf = SubstringSignal(query=query)
  assert list(result) == [
    {
      'text': enriched_item(
        'This has _underscore_', {expected_signal_udf.key(): [lilac_span(9, 21)]}
      )
    }
  ]


def test_search_keyword_multiple(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data(TEST_DATA)

  query_world = 'world'
  query_looking_world = 'looking for world'
  expected_world_udf = SubstringSignal(query=query_world)
  expected_again_looking_udf = SubstringSignal(query=query_looking_world)

  result = dataset.select_rows(
    searches=[
      KeywordSearch(path='text', query=query_world),
      KeywordSearch(path='text2', query=query_looking_world),
    ],
    combine_columns=True,
  )

  assert list(result) == [
    {
      'text': enriched_item(
        'looking for world in text', {expected_world_udf.key(): [lilac_span(12, 17)]}
      ),
      'text2': enriched_item(
        'again looking for world in text', {expected_again_looking_udf.key(): [lilac_span(6, 23)]}
      ),
    }
  ]


def test_search_keyword_with_filters(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data(TEST_DATA)

  query = 'world'
  result = dataset.select_rows(
    ['*'],
    filters=[(ROWID, 'in', ['1', '3'])],
    searches=[KeywordSearch(path='text', query=query)],
    combine_columns=True,
  )

  expected_signal_udf = SubstringSignal(query=query)
  assert list(result) == [
    {
      'text': enriched_item('hello world', {expected_signal_udf.key(): [lilac_span(6, 11)]}),
      'text2': 'again hello world',
    }
    # The second row doesn't match the rowid filter.
  ]


class TestEmbedding(TextEmbeddingSignal):
  """A test embed function."""

  name: ClassVar[str] = 'test_embedding'

  @override
  def compute(self, data: Iterable[RichData]) -> Iterable[Item]:
    """Call the embedding function."""
    for example in data:
      embedding = np.array(STR_EMBEDDINGS[cast(str, example)])
      yield [lilac_embedding(0, len(example), embedding)]


def test_semantic_search(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data([{'text': 'hello world.'}, {'text': 'hello world2.'}])

  test_embedding = TestEmbedding()
  dataset.compute_signal(test_embedding, ('text'))

  query = 'hello2.'
  result = dataset.select_rows(
    searches=[SemanticSearch(path='text', query=query, embedding='test_embedding')],
    combine_columns=True,
  )
  expected_signal_udf = SemanticSimilaritySignal(query=query, embedding='test_embedding')
  assert list(result) == [
    # Results are sorted by score desc.
    {
      'text': enriched_item(
        'hello world2.', {expected_signal_udf.key(): [lilac_span(0, 13, {'score': 3})]}
      )
    },
    {
      'text': enriched_item(
        'hello world.', {expected_signal_udf.key(): [lilac_span(0, 12, {'score': 2})]}
      )
    },
  ]


def test_concept_search(make_test_data: TestDataMaker, mocker: MockerFixture) -> None:
  concept_model_mock = mocker.spy(LogisticEmbeddingModel, 'fit')

  dataset = make_test_data(
    [
      {'text': 'hello world.'},
      {'text': 'hello world2.'},
      {'text': 'random negative 1'},
      {'text': 'random negative 2'},
      {'text': 'random negative 3'},
      {'text': 'random negative 4'},
    ]
  )

  test_embedding = TestEmbedding()
  dataset.compute_signal(test_embedding, ('text'))

  concept_db = DiskConceptDB()
  concept_db.create(namespace='test_namespace', name='test_concept', type=SignalInputType.TEXT)
  concept_db.edit(
    'test_namespace',
    'test_concept',
    ConceptUpdate(
      insert=[
        ExampleIn(label=False, text='hello world.'),
        ExampleIn(label=True, text='hello world2.'),
      ]
    ),
  )

  result = dataset.select_rows(
    columns=[ROWID, '*'],
    searches=[
      ConceptSearch(
        path='text',
        concept_namespace='test_namespace',
        concept_name='test_concept',
        embedding='test_embedding',
      )
    ],
    filters=[(ROWID, 'in', ['1', '2'])],
    combine_columns=True,
  )
  expected_signal_udf = ConceptSignal(
    namespace='test_namespace', concept_name='test_concept', embedding='test_embedding'
  )

  assert list(result) == [
    # Results are sorted by score desc.
    {
      ROWID: '2',
      'text': enriched_item(
        'hello world2.',
        {
          expected_signal_udf.key(): [lilac_span(0, 13, {'score': approx(0.75, abs=0.25)})],
          'test_namespace/test_concept/labels/preview': [lilac_span(0, 13, {'label': True})],
        },
      ),
    },
    {
      ROWID: '1',
      'text': enriched_item(
        'hello world.',
        {
          expected_signal_udf.key(): [lilac_span(0, 12, {'score': approx(0.25, abs=0.25)})],
          'test_namespace/test_concept/labels/preview': [lilac_span(0, 12, {'label': False})],
        },
      ),
    },
  ]

  (_, embeddings, labels) = concept_model_mock.call_args_list[-1].args
  assert embeddings.shape == (2, 3)
  assert labels == [
    # Explicit labels.
    False,
    True,
  ]


def test_concept_search_without_rowid(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data([{'text': 'hello world.'}, {'text': 'hello world2.'}])

  test_embedding = TestEmbedding()
  dataset.compute_signal(test_embedding, ('text'))

  concept_db = DiskConceptDB()
  concept_db.create(namespace='test_namespace', name='test_concept', type=SignalInputType.TEXT)
  concept_db.edit(
    'test_namespace',
    'test_concept',
    ConceptUpdate(
      insert=[
        ExampleIn(label=False, text='hello world.'),
        ExampleIn(label=True, text='hello world2.'),
      ]
    ),
  )

  result = dataset.select_rows(
    columns=['text'],
    searches=[
      ConceptSearch(
        path='text',
        concept_namespace='test_namespace',
        concept_name='test_concept',
        embedding='test_embedding',
      )
    ],
  )

  assert list(result) == [
    # Results are sorted by score desc.
    {
      'text': 'hello world2.',
      'text.test_namespace/test_concept/test_embedding/preview': [
        lilac_span(0, 13, {'score': approx(0.75, abs=0.25)})
      ],
      'text.test_namespace/test_concept/labels/preview': [lilac_span(0, 13, {'label': True})],
    },
    {
      'text': 'hello world.',
      'text.test_namespace/test_concept/test_embedding/preview': [
        lilac_span(0, 12, {'score': approx(0.25, abs=0.25)})
      ],
      'text.test_namespace/test_concept/labels/preview': [lilac_span(0, 12, {'label': False})],
    },
  ]

  result = dataset.select_rows(
    columns=['text'],
    searches=[
      ConceptSearch(
        path='text',
        concept_namespace='test_namespace',
        concept_name='test_concept',
        embedding='test_embedding',
      )
    ],
    combine_columns=True,
  )

  assert list(result) == [
    # Results are sorted by score desc.
    {
      'text': enriched_item(
        'hello world2.',
        {
          'test_namespace/test_concept/test_embedding/preview': [
            lilac_span(0, 13, {'score': approx(0.75, abs=0.25)})
          ],
          'test_namespace/test_concept/labels/preview': [lilac_span(0, 13, {'label': True})],
        },
      )
    },
    {
      'text': enriched_item(
        'hello world.',
        {
          'test_namespace/test_concept/test_embedding/preview': [
            lilac_span(0, 12, {'score': approx(0.25, abs=0.25)})
          ],
          'test_namespace/test_concept/labels/preview': [lilac_span(0, 12, {'label': False})],
        },
      )
    },
  ]


def test_concept_search_sort_by_rowid(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data([{'text': 'hello world.'}, {'text': 'hello world2.'}])

  test_embedding = TestEmbedding()
  dataset.compute_signal(test_embedding, ('text'))

  concept_db = DiskConceptDB()
  concept_db.create(namespace='test_namespace', name='test_concept', type=SignalInputType.TEXT)
  concept_db.edit(
    'test_namespace',
    'test_concept',
    ConceptUpdate(
      insert=[
        ExampleIn(label=False, text='hello world.'),
        ExampleIn(label=True, text='hello world2.'),
      ]
    ),
  )

  result = dataset.select_rows(
    columns=['text'],
    searches=[
      ConceptSearch(
        path='text',
        concept_namespace='test_namespace',
        concept_name='test_concept',
        embedding='test_embedding',
      )
    ],
    sort_by=[ROWID],
    sort_order=SortOrder.ASC,
  )

  assert list(result) == [
    # Results are sorted by rowid.
    {
      'text': 'hello world.',
      'text.test_namespace/test_concept/test_embedding/preview': [
        lilac_span(0, 12, {'score': approx(0.25, abs=0.25)})
      ],
      'text.test_namespace/test_concept/labels/preview': [lilac_span(0, 12, {'label': False})],
    },
    {
      'text': 'hello world2.',
      'text.test_namespace/test_concept/test_embedding/preview': [
        lilac_span(0, 13, {'score': approx(0.75, abs=0.25)})
      ],
      'text.test_namespace/test_concept/labels/preview': [lilac_span(0, 13, {'label': True})],
    },
  ]


def test_concept_search_over_repeated_string(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data(
    [{'text': ['hello.', 'hello world.']}, {'text': ['hello2.', 'hello world2.']}]
  )
  dataset.compute_embedding('test_embedding', ('text', '*'))

  concept_db = DiskConceptDB()
  concept_db.create(namespace='test_namespace', name='test_concept', type=SignalInputType.TEXT)
  concept_db.edit(
    'test_namespace',
    'test_concept',
    ConceptUpdate(
      insert=[
        ExampleIn(label=False, text='hello world.'),
        ExampleIn(label=True, text='hello world2.'),
      ]
    ),
  )

  result = dataset.select_rows(
    columns=['text'],
    searches=[
      ConceptSearch(
        path=('text', '*'),
        concept_namespace='test_namespace',
        concept_name='test_concept',
        embedding='test_embedding',
      )
    ],
    filters=[Filter(path=(ROWID,), op='in', value=['1', '2'])],
  )
  assert list(result) == [
    {
      'text': ['hello.', 'hello world.'],
      'text.test_namespace/test_concept/labels/preview': [
        None,
        [{'__span__': {'end': 12, 'start': 0}, 'label': False}],
      ],
      'text.test_namespace/test_concept/test_embedding/preview': [
        [{'__span__': {'end': 6, 'start': 0}, 'score': approx(0.93, abs=0.01)}],
        [{'__span__': {'end': 12, 'start': 0}, 'score': approx(0.26, abs=0.01)}],
      ],
    },
    {
      'text': ['hello2.', 'hello world2.'],
      'text.test_namespace/test_concept/labels/preview': [
        None,
        [{'__span__': {'end': 13, 'start': 0}, 'label': True}],
      ],
      'text.test_namespace/test_concept/test_embedding/preview': [
        [{'__span__': {'end': 7, 'start': 0}, 'score': approx(0.68, abs=0.01)}],
        [{'__span__': {'end': 13, 'start': 0}, 'score': approx(0.82, abs=0.01)}],
      ],
    },
  ]


def test_sort_override_search(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data(
    [{'text': 'hello world.', 'value': 10}, {'text': 'hello world2.', 'value': 20}]
  )

  test_embedding = TestEmbedding()
  dataset.compute_signal(test_embedding, ('text'))

  query = 'hello2.'
  search = SemanticSearch(path='text', query=query, embedding='test_embedding')

  expected_signal_udf = SemanticSimilaritySignal(query=query, embedding='test_embedding')
  expected_item_1 = {
    'text': enriched_item(
      'hello world.', {expected_signal_udf.key(): [lilac_span(0, 12, {'score': 2.0})]}
    ),
    'value': 10,
  }
  expected_item_2 = {
    'text': enriched_item(
      'hello world2.', {expected_signal_udf.key(): [lilac_span(0, 13, {'score': 3.0})]}
    ),
    'value': 20,
  }

  sort_order = SortOrder.ASC
  result = dataset.select_rows(
    searches=[search], sort_by=[('value',)], sort_order=sort_order, combine_columns=True
  )
  assert list(result) == [
    # Results are sorted by score ascending.
    expected_item_1,
    expected_item_2,
  ]

  sort_order = SortOrder.DESC
  result = dataset.select_rows(
    searches=[search], sort_by=[('text',)], sort_order=sort_order, combine_columns=True
  )
  assert list(result) == [
    # Results are sorted by score descending.
    expected_item_2,
    expected_item_1,
  ]


def test_search_keyword_and_semantic(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data([{'text': 'hello world.'}, {'text': 'hello world2.'}])

  test_embedding = TestEmbedding()
  dataset.compute_signal(test_embedding, ('text'))

  query = 'hello2.'
  keyword_query = 'rld2'
  result = dataset.select_rows(
    searches=[
      SemanticSearch(path='text', query=query, embedding='test_embedding'),
      KeywordSearch(path='text', query=keyword_query),
    ],
    combine_columns=True,
  )
  expected_semantic_signal = SemanticSimilaritySignal(query=query, embedding='test_embedding')
  expected_keyword_signal = SubstringSignal(query=keyword_query)
  assert list(result) == [
    # Results are sorted by score desc.
    {
      'text': enriched_item(
        'hello world2.',
        {
          expected_semantic_signal.key(): [lilac_span(0, 13, {'score': 3})],
          expected_keyword_signal.key(): [lilac_span(8, 12)],
        },
      )
    }
    # rowid '1' is not returned because it does not match the keyword query.
  ]
