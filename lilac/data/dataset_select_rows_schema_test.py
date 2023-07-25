"""Tests for `db.select_rows_schema()`."""

from typing import Iterable, Optional, cast

import numpy as np
import pytest
from typing_extensions import override

from ..embeddings.vector_store import VectorStore
from ..schema import PATH_WILDCARD, UUID_COLUMN, Field, Item, RichData, VectorKey, field, schema
from ..signals.concept_labels import ConceptLabelsSignal
from ..signals.concept_scorer import ConceptScoreSignal
from ..signals.semantic_similarity import SemanticSimilaritySignal
from ..signals.signal import (
  EMBEDDING_KEY,
  TextEmbeddingModelSignal,
  TextEmbeddingSignal,
  TextSignal,
  TextSplitterSignal,
  clear_signal_registry,
  register_signal,
)
from ..signals.substring_search import SubstringSignal
from .dataset import (
  Column,
  ConceptQuery,
  KeywordQuery,
  Search,
  SearchResultInfo,
  SelectRowsSchemaResult,
  SelectRowsSchemaUDF,
  SemanticQuery,
  SortOrder,
  SortResult,
)
from .dataset_test_utils import TestDataMaker, enriched_embedding_span_field
from .dataset_utils import lilac_embedding, lilac_span

TEST_DATA: list[Item] = [{
  UUID_COLUMN: '1',
  'erased': False,
  'people': [{
    'name': 'A',
    'zipcode': 0,
    'locations': [{
      'city': 'city1',
      'state': 'state1'
    }, {
      'city': 'city2',
      'state': 'state2'
    }]
  }]
}, {
  UUID_COLUMN: '2',
  'erased': True,
  'people': [{
    'name': 'B',
    'zipcode': 1,
    'locations': [{
      'city': 'city3',
      'state': 'state3'
    }, {
      'city': 'city4'
    }, {
      'city': 'city5'
    }]
  }, {
    'name': 'C',
    'zipcode': 2,
    'locations': [{
      'city': 'city1',
      'state': 'state1'
    }]
  }]
}]


class TestSplitter(TextSplitterSignal):
  """Split documents into sentence by splitting on period."""
  name = 'test_splitter'

  @override
  def compute(self, data: Iterable[RichData]) -> Iterable[Item]:
    for text in data:
      if not isinstance(text, str):
        raise ValueError(f'Expected text to be a string, got {type(text)} instead.')
      sentences = [f'{sentence.strip()}.' for sentence in text.split('.') if sentence]
      yield [
        lilac_span(text.index(sentence),
                   text.index(sentence) + len(sentence)) for sentence in sentences
      ]


EMBEDDINGS: list[tuple[str, list[float]]] = [('hello.', [1.0, 0.0, 0.0]),
                                             ('hello2.', [1.0, 1.0, 0.0]),
                                             ('hello world.', [1.0, 1.0, 1.0]),
                                             ('hello world2.', [2.0, 1.0, 1.0])]

STR_EMBEDDINGS: dict[str, list[float]] = {text: embedding for text, embedding in EMBEDDINGS}


class TestEmbedding(TextEmbeddingSignal):
  """A test embed function."""
  name = 'test_embedding'

  @override
  def compute(self, data: Iterable[RichData]) -> Iterable[Item]:
    """Call the embedding function."""
    for example in data:
      yield [lilac_embedding(0, len(example), np.array(STR_EMBEDDINGS[cast(str, example)]))]


class TestEmbeddingSumSignal(TextEmbeddingModelSignal):
  """Sums the embeddings to return a single floating point value."""
  name = 'test_embedding_sum'

  @override
  def fields(self) -> Field:
    return field('float32')

  @override
  def vector_compute(self, keys: Iterable[VectorKey], vector_store: VectorStore) -> Iterable[Item]:
    # The signal just sums the values of the embedding.
    embedding_sums = vector_store.get(keys).sum(axis=1)
    for embedding_sum in embedding_sums.tolist():
      yield embedding_sum


@pytest.fixture(scope='module', autouse=True)
def setup_teardown() -> Iterable[None]:
  # Setup.
  register_signal(LengthSignal)
  register_signal(AddSpaceSignal)
  register_signal(TestSplitter)
  register_signal(TestEmbedding)
  register_signal(TestEmbeddingSumSignal)

  # Unit test runs.
  yield

  # Teardown.
  clear_signal_registry()


class LengthSignal(TextSignal):
  name = 'length_signal'

  def fields(self) -> Field:
    return field('int32')

  def compute(self, data: Iterable[RichData]) -> Iterable[Optional[Item]]:
    for text_content in data:
      yield len(text_content)


class AddSpaceSignal(TextSignal):
  name = 'add_space_signal'

  def fields(self) -> Field:
    return field('string')

  def compute(self, data: Iterable[RichData]) -> Iterable[Optional[Item]]:
    for text_content in data:
      yield cast(str, text_content) + ' '


def test_simple_schema(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data(TEST_DATA)
  result = dataset.select_rows_schema(combine_columns=True)
  assert result == SelectRowsSchemaResult(
    data_schema=schema({
      UUID_COLUMN: 'string',
      'erased': 'boolean',
      'people': [{
        'name': 'string',
        'zipcode': 'int32',
        'locations': [{
          'city': 'string',
          'state': 'string'
        }]
      }]
    }))


def test_subselection_with_combine_cols(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data(TEST_DATA)

  result = dataset.select_rows_schema([('people', '*', 'zipcode'),
                                       ('people', '*', 'locations', '*', 'city')],
                                      combine_columns=True)
  assert result == SelectRowsSchemaResult(
    data_schema=schema({
      UUID_COLUMN: 'string',
      'people': [{
        'zipcode': 'int32',
        'locations': [{
          'city': 'string'
        }]
      }]
    }))

  result = dataset.select_rows_schema([('people', '*', 'name'), ('people', '*', 'locations')],
                                      combine_columns=True)
  assert result == SelectRowsSchemaResult(
    data_schema=schema({
      UUID_COLUMN: 'string',
      'people': [{
        'name': 'string',
        'locations': [{
          'city': 'string',
          'state': 'string'
        }]
      }]
    }))

  result = dataset.select_rows_schema([('people', '*')], combine_columns=True)
  assert result == SelectRowsSchemaResult(
    data_schema=schema({
      UUID_COLUMN: 'string',
      'people': [{
        'name': 'string',
        'zipcode': 'int32',
        'locations': [{
          'city': 'string',
          'state': 'string'
        }]
      }]
    }))


def test_udf_with_combine_cols(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data(TEST_DATA)

  length_signal = LengthSignal()
  result = dataset.select_rows_schema([('people', '*', 'locations', '*', 'city'),
                                       Column(('people', '*', 'name'), signal_udf=length_signal)],
                                      combine_columns=True)
  assert result == SelectRowsSchemaResult(
    data_schema=schema({
      UUID_COLUMN: 'string',
      'people': [{
        'name': {
          'length_signal': field('int32', length_signal.dict())
        },
        'locations': [{
          'city': 'string'
        }]
      }],
    }),
    udfs=[
      SelectRowsSchemaUDF(path=('people', '*', 'name', length_signal.key())),
    ],
  )


def test_embedding_udf_with_combine_cols(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data(TEST_DATA)

  add_space_signal = AddSpaceSignal()
  path = ('people', '*', 'name')
  dataset.compute_signal(add_space_signal, path)
  result = dataset.select_rows_schema([path, Column(path, signal_udf=add_space_signal)],
                                      combine_columns=True)
  assert result == SelectRowsSchemaResult(
    data_schema=schema({
      UUID_COLUMN: 'string',
      'people': [{
        'name': field(
          'string', fields={'add_space_signal': field('string', signal=add_space_signal.dict())})
      }],
    }),
    udfs=[
      SelectRowsSchemaUDF(path=(*path, add_space_signal.key())),
    ],
  )


def test_udf_chained_with_combine_cols(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data([{
    UUID_COLUMN: '1',
    'text': 'hello. hello2.',
  }, {
    UUID_COLUMN: '2',
    'text': 'hello world. hello world2.',
  }])

  test_splitter = TestSplitter()
  dataset.compute_signal(test_splitter, ('text'))
  add_space_signal = AddSpaceSignal()
  result = dataset.select_rows_schema(
    [('text'), Column(('text'), signal_udf=add_space_signal)], combine_columns=True)

  assert result == SelectRowsSchemaResult(
    data_schema=schema({
      UUID_COLUMN: 'string',
      'text': field(
        'string',
        fields={
          'add_space_signal': field('string', add_space_signal.dict()),
          'test_splitter': field(signal=test_splitter.dict(), fields=['string_span'])
        })
    }),
    udfs=[
      SelectRowsSchemaUDF(path=('text', add_space_signal.key())),
    ],
  )


def test_udf_embedding_chained_with_combine_cols(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data([{
    UUID_COLUMN: '1',
    'text': 'hello. hello2.',
  }, {
    UUID_COLUMN: '2',
    'text': 'hello world. hello world2.',
  }])

  test_splitter = TestSplitter()
  dataset.compute_signal(test_splitter, 'text')
  test_embedding = TestEmbedding()
  dataset.compute_signal(test_embedding, ('text', 'test_splitter', '*'))

  embedding_sum_signal = TestEmbeddingSumSignal(embedding='test_embedding')
  udf_col = Column(('text', 'test_splitter', '*'), signal_udf=embedding_sum_signal)
  result = dataset.select_rows_schema([('text'), udf_col], combine_columns=True)

  expected_schema = schema({
    UUID_COLUMN: 'string',
    'text': field(
      'string',
      fields={
        'test_splitter': field(
          signal=test_splitter.dict(),
          fields=[
            field(
              'string_span',
              fields={
                'test_embedding': field(
                  signal=test_embedding.dict(),
                  fields=[
                    enriched_embedding_span_field(
                      {'test_embedding_sum': field('float32', embedding_sum_signal.dict())})
                  ])
              })
          ])
      })
  })
  output_path = ('text', 'test_splitter', '*', 'test_embedding', '*', 'embedding',
                 'test_embedding_sum')
  assert result == SelectRowsSchemaResult(
    data_schema=expected_schema,
    udfs=[SelectRowsSchemaUDF(path=output_path)],
  )

  # Alias the udf.
  udf_col.alias = 'udf1'
  result = dataset.select_rows_schema([('text'), udf_col], combine_columns=True)
  assert result == SelectRowsSchemaResult(
    data_schema=expected_schema,
    udfs=[SelectRowsSchemaUDF(path=output_path, alias='udf1')],
  )


def test_search_keyword_schema(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data([{
    UUID_COLUMN: '1',
    'text': 'hello world',
    'text2': 'hello world2',
  }])
  query_world = 'world'
  query_hello = 'hello'

  result = dataset.select_rows_schema(
    searches=[
      Search(path='text', query=KeywordQuery(type='keyword', search=query_world)),
      Search(path='text2', query=KeywordQuery(type='keyword', search=query_hello)),
    ],
    combine_columns=True)

  expected_world_signal = SubstringSignal(query=query_world)
  expected_hello_signal = SubstringSignal(query=query_hello)

  assert result == SelectRowsSchemaResult(
    data_schema=schema({
      UUID_COLUMN: 'string',
      'text': field(
        'string',
        fields={
          expected_world_signal.key(): field(
            signal=expected_world_signal.dict(), fields=['string_span'])
        }),
      'text2': field(
        'string',
        fields={
          expected_hello_signal.key(): field(
            signal=expected_hello_signal.dict(), fields=['string_span'])
        })
    }),
    search_results=[
      SearchResultInfo(
        search_path=('text',),
        result_path=('text', expected_world_signal.key(), PATH_WILDCARD),
      ),
      SearchResultInfo(
        search_path=('text2',),
        result_path=('text2', expected_hello_signal.key(), PATH_WILDCARD),
      )
    ],
    udfs=[
      SelectRowsSchemaUDF(path=('text', expected_world_signal.key())),
      SelectRowsSchemaUDF(path=('text2', expected_hello_signal.key())),
    ],
  )


def test_search_semantic_schema(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data([{
    UUID_COLUMN: '1',
    'text': 'hello world.',
  }])
  query_world = 'world'

  test_embedding = TestEmbedding()
  dataset.compute_signal(test_embedding, ('text'))

  result = dataset.select_rows_schema(
    searches=[
      Search(
        path='text',
        query=SemanticQuery(type='semantic', search=query_world, embedding='test_embedding')),
    ],
    combine_columns=True)

  test_embedding = TestEmbedding()
  expected_world_signal = SemanticSimilaritySignal(query=query_world, embedding='test_embedding')

  similarity_score_path = ('text', 'test_embedding', PATH_WILDCARD, EMBEDDING_KEY,
                           expected_world_signal.key())
  assert result == SelectRowsSchemaResult(
    data_schema=schema({
      UUID_COLUMN: 'string',
      'text': field(
        'string',
        fields={
          'test_embedding': field(
            signal=test_embedding.dict(),
            fields=[
              enriched_embedding_span_field(
                {expected_world_signal.key(): field('float32', expected_world_signal.dict())})
            ])
        })
    }),
    udfs=[SelectRowsSchemaUDF(path=similarity_score_path)],
    search_results=[SearchResultInfo(search_path=('text',), result_path=similarity_score_path)],
    sorts=[SortResult(path=similarity_score_path, order=SortOrder.DESC, search_index=0)])


def test_search_concept_schema(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data([{
    UUID_COLUMN: '1',
    'text': 'hello world.',
  }])

  test_embedding = TestEmbedding()
  dataset.compute_signal(test_embedding, ('text'))

  result = dataset.select_rows_schema(
    searches=[
      Search(
        path='text',
        query=ConceptQuery(
          type='concept',
          concept_namespace='test_namespace',
          concept_name='test_concept',
          embedding='test_embedding')),
    ],
    combine_columns=True)

  test_embedding = TestEmbedding()
  expected_world_signal = ConceptScoreSignal(
    namespace='test_namespace', concept_name='test_concept', embedding='test_embedding')
  expected_labels_signal = ConceptLabelsSignal(
    namespace='test_namespace', concept_name='test_concept')

  concept_score_path = ('text', 'test_embedding', PATH_WILDCARD, EMBEDDING_KEY,
                        expected_world_signal.key())
  concept_labels_path = ('text', expected_labels_signal.key())
  assert result == SelectRowsSchemaResult(
    data_schema=schema({
      UUID_COLUMN: 'string',
      'text': field(
        'string',
        fields={
          'test_embedding': field(
            signal=test_embedding.dict(),
            fields=[
              enriched_embedding_span_field({
                expected_world_signal.key(): field(
                  'float32',
                  expected_world_signal.dict(),
                  bins=[('Not in concept', None, 0.5), ('In concept', 0.5, None)])
              })
            ]),
          'test_namespace/test_concept/labels': field(
            fields=[field('string_span', fields={
              'label': 'boolean',
              'draft': 'string'
            })],
            signal=expected_labels_signal.dict())
        })
    }),
    udfs=[
      SelectRowsSchemaUDF(path=concept_labels_path),
      SelectRowsSchemaUDF(path=concept_score_path)
    ],
    search_results=[
      SearchResultInfo(search_path=('text',), result_path=concept_labels_path),
      SearchResultInfo(search_path=('text',), result_path=concept_score_path)
    ],
    sorts=[SortResult(path=concept_score_path, order=SortOrder.DESC, search_index=0)])


def test_search_sort_override(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data([{
    UUID_COLUMN: '1',
    'text': 'hello world.',
  }])
  query_world = 'world'

  test_embedding = TestEmbedding()
  dataset.compute_signal(test_embedding, ('text'))

  result = dataset.select_rows_schema(
    searches=[
      Search(
        path='text',
        query=SemanticQuery(type='semantic', search=query_world, embedding='test_embedding')),
    ],
    # Explicit sort by overrides the semantic search.
    sort_by=[('text',)],
    sort_order=SortOrder.DESC,
    combine_columns=True)

  assert result.sorts == [SortResult(path=('text',), order=SortOrder.DESC)]
