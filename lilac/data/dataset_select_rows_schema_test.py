"""Tests for `db.select_rows_schema()`."""

from typing import ClassVar, Iterable, Optional, cast

import numpy as np
import pytest
from typing_extensions import override

from ..embeddings.vector_store import VectorDBIndex
from ..schema import (
  EMBEDDING_KEY,
  PATH_WILDCARD,
  Field,
  Item,
  RichData,
  SignalInputType,
  VectorKey,
  field,
  lilac_embedding,
  lilac_span,
  schema,
)
from ..signal import (
  TextEmbeddingSignal,
  TextSignal,
  VectorSignal,
  clear_signal_registry,
  register_signal,
)
from ..signals.concept_labels import ConceptLabelsSignal
from ..signals.concept_scorer import ConceptSignal
from ..signals.semantic_similarity import SemanticSimilaritySignal
from ..signals.substring_search import SubstringSignal
from .dataset import (
  Column,
  ConceptSearch,
  KeywordSearch,
  SearchResultInfo,
  SelectRowsSchemaResult,
  SelectRowsSchemaUDF,
  SemanticSearch,
  SortOrder,
  SortResult,
)
from .dataset_test_utils import TestDataMaker

TEST_DATA: list[Item] = [
  {
    'erased': False,
    'people': [
      {
        'name': 'A',
        'zipcode': 0,
        'locations': [{'city': 'city1', 'state': 'state1'}, {'city': 'city2', 'state': 'state2'}],
      }
    ],
  },
  {
    'erased': True,
    'people': [
      {
        'name': 'B',
        'zipcode': 1,
        'locations': [{'city': 'city3', 'state': 'state3'}, {'city': 'city4'}, {'city': 'city5'}],
      },
      {'name': 'C', 'zipcode': 2, 'locations': [{'city': 'city1', 'state': 'state1'}]},
    ],
  },
]


class TestSplitter(TextSignal):
  """Split documents into sentence by splitting on period."""

  name: ClassVar[str] = 'test_splitter'

  @override
  def fields(self) -> Field:
    return field(fields=['string_span'])

  @override
  def compute(self, data: Iterable[RichData]) -> Iterable[Item]:
    for text in data:
      if not isinstance(text, str):
        raise ValueError(f'Expected text to be a string, got {type(text)} instead.')
      sentences = [f'{sentence.strip()}.' for sentence in text.split('.') if sentence]
      yield [
        lilac_span(text.index(sentence), text.index(sentence) + len(sentence))
        for sentence in sentences
      ]


EMBEDDINGS: list[tuple[str, list[float]]] = [
  ('hello.', [1.0, 0.0, 0.0]),
  ('hello2.', [1.0, 1.0, 0.0]),
  ('hello world.', [1.0, 1.0, 1.0]),
  ('hello world2.', [2.0, 1.0, 1.0]),
]

STR_EMBEDDINGS: dict[str, list[float]] = {text: embedding for text, embedding in EMBEDDINGS}


class TestEmbedding(TextEmbeddingSignal):
  """A test embed function."""

  name: ClassVar[str] = 'test_embedding'

  @override
  def compute(self, data: Iterable[RichData]) -> Iterable[Item]:
    """Call the embedding function."""
    for example in data:
      yield [lilac_embedding(0, len(example), np.array(STR_EMBEDDINGS[cast(str, example)]))]


class TestEmbeddingSumSignal(VectorSignal):
  """Sums the embeddings to return a single floating point value."""

  name: ClassVar[str] = 'test_embedding_sum'
  input_type: ClassVar[SignalInputType] = SignalInputType.TEXT

  @override
  def fields(self) -> Field:
    return field('float32')

  @override
  def vector_compute(
    self, keys: Iterable[VectorKey], vector_index: VectorDBIndex
  ) -> Iterable[Item]:
    # The signal just sums the values of the embedding.
    all_vector_spans = vector_index.get(keys)
    for vector_spans in all_vector_spans:
      yield vector_spans[0]['vector'].sum()


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
  name: ClassVar[str] = 'length_signal'

  def fields(self) -> Field:
    return field('int32')

  def compute(self, data: Iterable[RichData]) -> Iterable[Optional[Item]]:
    for text_content in data:
      yield len(text_content)


class AddSpaceSignal(TextSignal):
  name: ClassVar[str] = 'add_space_signal'

  def fields(self) -> Field:
    return field('string')

  def compute(self, data: Iterable[RichData]) -> Iterable[Optional[Item]]:
    for text_content in data:
      yield cast(str, text_content) + ' '


def test_simple_schema(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data(TEST_DATA)
  result = dataset.select_rows_schema(combine_columns=True)
  assert result == SelectRowsSchemaResult(
    data_schema=schema(
      {
        'erased': 'boolean',
        'people': [
          {
            'name': 'string',
            'zipcode': 'int32',
            'locations': [{'city': 'string', 'state': 'string'}],
          }
        ],
      }
    )
  )


def test_subselection_with_combine_cols(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data(TEST_DATA)

  result = dataset.select_rows_schema(
    [('people', '*', 'zipcode'), ('people', '*', 'locations', '*', 'city')], combine_columns=True
  )
  assert result == SelectRowsSchemaResult(
    data_schema=schema({'people': [{'zipcode': 'int32', 'locations': [{'city': 'string'}]}]})
  )

  result = dataset.select_rows_schema(
    [('people', '*', 'name'), ('people', '*', 'locations')], combine_columns=True
  )
  assert result == SelectRowsSchemaResult(
    data_schema=schema(
      {'people': [{'name': 'string', 'locations': [{'city': 'string', 'state': 'string'}]}]}
    )
  )

  result = dataset.select_rows_schema([('people', '*')], combine_columns=True)
  assert result == SelectRowsSchemaResult(
    data_schema=schema(
      {
        'people': [
          {
            'name': 'string',
            'zipcode': 'int32',
            'locations': [{'city': 'string', 'state': 'string'}],
          }
        ]
      }
    )
  )


def test_udf_with_combine_cols(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data(TEST_DATA)

  length_signal = LengthSignal()
  result = dataset.select_rows_schema(
    [
      ('people', '*', 'locations', '*', 'city'),
      Column(('people', '*', 'name'), signal_udf=length_signal),
    ],
    combine_columns=True,
  )
  assert result == SelectRowsSchemaResult(
    data_schema=schema(
      {
        'people': [
          {
            'name': {'length_signal': field('int32', length_signal.model_dump())},
            'locations': [{'city': 'string'}],
          }
        ]
      }
    ),
    udfs=[SelectRowsSchemaUDF(path=('people', '*', 'name', length_signal.key()))],
  )


def test_embedding_udf_with_combine_cols(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data(TEST_DATA)

  add_space_signal = AddSpaceSignal()
  path = ('people', '*', 'name')
  dataset.compute_signal(add_space_signal, path)
  result = dataset.select_rows_schema(
    [path, Column(path, signal_udf=add_space_signal)], combine_columns=True
  )
  assert result == SelectRowsSchemaResult(
    data_schema=schema(
      {
        'people': [
          {
            'name': field(
              'string',
              fields={'add_space_signal': field('string', signal=add_space_signal.model_dump())},
            )
          }
        ]
      }
    ),
    udfs=[SelectRowsSchemaUDF(path=(*path, add_space_signal.key()))],
  )


def test_udf_chained_with_combine_cols(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data([{'text': 'hello. hello2.'}, {'text': 'hello world. hello world2.'}])

  test_splitter = TestSplitter()
  dataset.compute_signal(test_splitter, ('text'))
  add_space_signal = AddSpaceSignal()
  result = dataset.select_rows_schema(
    [('text'), Column(('text'), signal_udf=add_space_signal)], combine_columns=True
  )

  assert result == SelectRowsSchemaResult(
    data_schema=schema(
      {
        'text': field(
          'string',
          fields={
            'add_space_signal': field('string', add_space_signal.model_dump()),
            'test_splitter': field(signal=test_splitter.model_dump(), fields=['string_span']),
          },
        )
      }
    ),
    udfs=[SelectRowsSchemaUDF(path=('text', add_space_signal.key()))],
  )


def test_search_keyword_schema(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data([{'text': 'hello world', 'text2': 'hello world2'}])
  query_world = 'world'
  query_hello = 'hello'

  result = dataset.select_rows_schema(
    searches=[
      KeywordSearch(path='text', query=query_world),
      KeywordSearch(path='text2', query=query_hello),
    ],
    combine_columns=True,
  )

  expected_world_signal = SubstringSignal(query=query_world)
  expected_hello_signal = SubstringSignal(query=query_hello)

  assert result == SelectRowsSchemaResult(
    data_schema=schema(
      {
        'text': field(
          'string',
          fields={
            expected_world_signal.key(): field(
              signal=expected_world_signal.model_dump(), fields=['string_span']
            )
          },
        ),
        'text2': field(
          'string',
          fields={
            expected_hello_signal.key(): field(
              signal=expected_hello_signal.model_dump(), fields=['string_span']
            )
          },
        ),
      }
    ),
    search_results=[
      SearchResultInfo(
        search_path=('text',), result_path=('text', expected_world_signal.key(), PATH_WILDCARD)
      ),
      SearchResultInfo(
        search_path=('text2',), result_path=('text2', expected_hello_signal.key(), PATH_WILDCARD)
      ),
    ],
    udfs=[
      SelectRowsSchemaUDF(path=('text', expected_world_signal.key())),
      SelectRowsSchemaUDF(path=('text2', expected_hello_signal.key())),
    ],
  )


def test_search_semantic_schema(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data([{'text': 'hello world.'}])
  query_world = 'world'

  test_embedding = TestEmbedding()
  dataset.compute_signal(test_embedding, ('text'))

  result = dataset.select_rows_schema(
    searches=[SemanticSearch(path='text', query=query_world, embedding='test_embedding')],
    combine_columns=True,
  )

  test_embedding = TestEmbedding()
  expected_world_signal = SemanticSimilaritySignal(query=query_world, embedding='test_embedding')

  similarity_score_path = ('text', expected_world_signal.key())
  assert result == SelectRowsSchemaResult(
    data_schema=schema(
      {
        'text': field(
          'string',
          fields={
            'test_embedding': field(
              signal=test_embedding.model_dump(),
              fields=[field('string_span', fields={EMBEDDING_KEY: 'embedding'})],
            ),
            expected_world_signal.key(): field(
              signal=expected_world_signal.model_dump(),
              fields=[field('string_span', fields={'score': 'float32'})],
            ),
          },
        )
      }
    ),
    udfs=[SelectRowsSchemaUDF(path=similarity_score_path)],
    search_results=[SearchResultInfo(search_path=('text',), result_path=similarity_score_path)],
    sorts=[
      SortResult(
        path=(*similarity_score_path, PATH_WILDCARD, 'score'), order=SortOrder.DESC, search_index=0
      )
    ],
  )


def test_search_concept_schema(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data([{'text': 'hello world.'}])

  test_embedding = TestEmbedding()
  dataset.compute_signal(test_embedding, ('text'))

  result = dataset.select_rows_schema(
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

  expected_world_signal = ConceptSignal(
    namespace='test_namespace', concept_name='test_concept', embedding='test_embedding'
  )
  expected_labels_signal = ConceptLabelsSignal(
    namespace='test_namespace', concept_name='test_concept'
  )

  concept_score_path = ('text', expected_world_signal.key())
  concept_labels_path = ('text', expected_labels_signal.key())
  assert result == SelectRowsSchemaResult(
    data_schema=schema(
      {
        'text': field(
          'string',
          fields={
            'test_embedding': field(
              signal=test_embedding.model_dump(),
              fields=[field('string_span', fields={EMBEDDING_KEY: 'embedding'})],
            ),
            expected_world_signal.key(): field(
              signal=expected_world_signal.model_dump(),
              fields=[
                field(
                  dtype='string_span',
                  fields={
                    'score': field(
                      'float32', bins=[('Not in concept', None, 0.5), ('In concept', 0.5, None)]
                    )
                  },
                )
              ],
            ),
            'test_namespace/test_concept/labels/preview': field(
              fields=[field('string_span', fields={'label': 'boolean', 'draft': 'string'})],
              signal=expected_labels_signal.model_dump(),
            ),
          },
        )
      }
    ),
    udfs=[
      SelectRowsSchemaUDF(path=concept_labels_path),
      SelectRowsSchemaUDF(path=concept_score_path),
    ],
    search_results=[
      SearchResultInfo(search_path=('text',), result_path=concept_labels_path),
      SearchResultInfo(search_path=('text',), result_path=concept_score_path),
    ],
    sorts=[
      SortResult(
        path=(*concept_score_path, PATH_WILDCARD, 'score'), order=SortOrder.DESC, search_index=0
      )
    ],
  )


def test_search_sort_override(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data([{'text': 'hello world.'}])
  query_world = 'world'

  test_embedding = TestEmbedding()
  dataset.compute_signal(test_embedding, ('text'))

  result = dataset.select_rows_schema(
    searches=[SemanticSearch(path='text', query=query_world, embedding='test_embedding')],
    # Explicit sort by overrides the semantic search.
    sort_by=[('text',)],
    sort_order=SortOrder.DESC,
    combine_columns=True,
  )

  assert result.sorts == [SortResult(path=('text',), order=SortOrder.DESC)]
