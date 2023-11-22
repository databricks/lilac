"""Implementation-agnostic tests of the Dataset DB API."""

from typing import ClassVar, Iterable, Optional, cast

import numpy as np
import pytest
from typing_extensions import override

from ..config import DatasetConfig, EmbeddingConfig, SignalConfig
from ..schema import (
  EMBEDDING_KEY,
  ROWID,
  Field,
  Item,
  MapType,
  RichData,
  field,
  lilac_embedding,
  schema,
)
from ..signal import TextEmbeddingSignal, TextSignal, clear_signal_registry, register_signal
from ..source import clear_source_registry, register_source
from .dataset import Column, DatasetManifest, dataset_config_from_manifest
from .dataset_test_utils import (
  TEST_DATASET_NAME,
  TEST_NAMESPACE,
  TestDataMaker,
  TestSource,
  enriched_item,
)

SIMPLE_ITEMS: list[Item] = [
  {'str': 'a', 'int': 1, 'bool': False, 'float': 3.0},
  {'str': 'b', 'int': 2, 'bool': True, 'float': 2.0},
  {'str': 'b', 'int': 2, 'bool': True, 'float': 1.0},
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


class LengthSignal(TextSignal):
  name: ClassVar[str] = 'length_signal'

  _call_count: int = 0

  def fields(self) -> Field:
    return field('int32')

  def compute(self, data: Iterable[RichData]) -> Iterable[Optional[Item]]:
    for text_content in data:
      self._call_count += 1
      yield len(text_content)


class TestSignal(TextSignal):
  name: ClassVar[str] = 'test_signal'

  @override
  def fields(self) -> Field:
    return field(fields={'len': 'int32', 'flen': 'float32'})

  @override
  def compute(self, data: Iterable[RichData]) -> Iterable[Optional[Item]]:
    return [{'len': len(text_content), 'flen': float(len(text_content))} for text_content in data]


@pytest.fixture(scope='module', autouse=True)
def setup_teardown() -> Iterable[None]:
  # Setup.
  register_source(TestSource)
  register_signal(TestSignal)
  register_signal(TestEmbedding)
  register_signal(LengthSignal)
  register_signal(SignalWithQuoteInIt)
  register_signal(SignalWithDoubleQuoteInIt)

  # Unit test runs.
  yield

  # Teardown.
  clear_source_registry()
  clear_signal_registry()


def test_select_all_columns(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data(SIMPLE_ITEMS)

  result = dataset.select_rows()
  assert list(result) == SIMPLE_ITEMS


def test_select_subcols_with_dot_seperator(make_test_data: TestDataMaker) -> None:
  items: list[Item] = [
    {'people': [{'name': 'A', 'address': {'zip': 1}}, {'name': 'B', 'address': {'zip': 2}}]},
    {'people': [{'name': 'C', 'address': {'zip': 3}}]},
  ]
  dataset = make_test_data(items)

  result = dataset.select_rows(['people.*.name', 'people.*.address.zip'])
  assert list(result) == [
    {'people.*.name': ['A', 'B'], 'people.*.address.zip': [1, 2]},
    {'people.*.name': ['C'], 'people.*.address.zip': [3]},
  ]

  result = dataset.select_rows(['people.*.address.zip'], combine_columns=True)
  assert list(result) == [
    {'people': [{'address': {'zip': 1}}, {'address': {'zip': 2}}]},
    {'people': [{'address': {'zip': 3}}]},
  ]

  result = dataset.select_rows(['people'])
  assert list(result) == items


def test_select_subcols_with_escaped_dot(make_test_data: TestDataMaker) -> None:
  items: list[Item] = [
    {'people.new': [{'name': 'A'}, {'name': 'B'}]},
    {'people.new': [{'name': 'C'}]},
  ]
  dataset = make_test_data(items)

  result = dataset.select_rows(['"people.new".*.name'])
  assert list(result) == [{'people.new.*.name': ['A', 'B']}, {'people.new.*.name': ['C']}]

  # Escape name even though it does not need to be.
  result = dataset.select_rows(['"people.new".*."name"'])
  assert list(result) == [{'people.new.*.name': ['A', 'B']}, {'people.new.*.name': ['C']}]


def test_select_star(make_test_data: TestDataMaker) -> None:
  items: list[Item] = [{'name': 'A', 'info': {'age': 40}}, {'name': 'B', 'info': {'age': 42}}]
  dataset = make_test_data(items)

  # Select *.
  result = dataset.select_rows(['*'])
  assert list(result) == [{'name': 'A', 'info.age': 40}, {'name': 'B', 'info.age': 42}]

  # Select (*,).
  result = dataset.select_rows([('*',)])
  assert list(result) == [{'name': 'A', 'info.age': 40}, {'name': 'B', 'info.age': 42}]

  # Select *, plus a redundant `info` column.
  result = dataset.select_rows(['*', 'info'])
  assert list(result) == [
    {'name': 'A', 'info.age': 40, 'info': {'age': 40}},
    {'name': 'B', 'info.age': 42, 'info': {'age': 42}},
  ]

  # Select * plus an inner `info.age` column.
  result = dataset.select_rows(['*', ('info', 'age')])
  assert list(result) == [
    {'info.age': 40, 'info.age_2': 40, 'name': 'A'},
    {'info.age': 42, 'info.age_2': 42, 'name': 'B'},
  ]


def test_select_star_with_combine_cols(make_test_data: TestDataMaker) -> None:
  items: list[Item] = [{'name': 'A', 'info': {'age': 40}}, {'name': 'B', 'info': {'age': 42}}]
  dataset = make_test_data(items)

  # Select *.
  result = dataset.select_rows(['*'], combine_columns=True)
  assert list(result) == items

  # Select *, plus a redundant `info` column.
  result = dataset.select_rows(['*', 'info'], combine_columns=True)
  assert list(result) == items

  # Select * plus an inner `info.age` column.
  result = dataset.select_rows(['*', ('info', 'age')], combine_columns=True)
  assert list(result) == items

  # Select *, plus redundant `name`, plus a udf.
  udf = Column('name', signal_udf=TestSignal())
  result = dataset.select_rows(['*', 'name', udf], combine_columns=True)

  assert list(result) == [
    {'name': enriched_item('A', {'test_signal': {'len': 1, 'flen': 1.0}}), 'info': {'age': 40}},
    {'name': enriched_item('B', {'test_signal': {'len': 1, 'flen': 1.0}}), 'info': {'age': 42}},
  ]


def test_select_ids(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data(SIMPLE_ITEMS)

  result = dataset.select_rows([ROWID])

  assert list(result) == [{ROWID: '1'}, {ROWID: '2'}, {ROWID: '3'}]


def test_select_ids_with_limit_and_offset(make_test_data: TestDataMaker) -> None:
  items: list[Item] = [{str(i): i} for i in range(9)]
  dataset = make_test_data(items)

  result = dataset.select_rows([ROWID], offset=1, limit=3)
  assert list(result) == [{ROWID: '2'}, {ROWID: '3'}, {ROWID: '4'}]

  result = dataset.select_rows([ROWID], offset=7, limit=2)
  assert list(result) == [{ROWID: '8'}, {ROWID: '9'}]

  result = dataset.select_rows([ROWID], offset=8, limit=200)
  assert list(result) == [{ROWID: '9'}]

  result = dataset.select_rows([ROWID], offset=9, limit=200)
  assert list(result) == []


def test_columns(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data(SIMPLE_ITEMS)

  result = dataset.select_rows([ROWID, 'str', 'float'])

  assert list(result) == [
    {ROWID: '1', 'str': 'a', 'float': 3.0},
    {ROWID: '2', 'str': 'b', 'float': 2.0},
    {ROWID: '3', 'str': 'b', 'float': 1.0},
  ]


def test_select_rows_iter(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data(SIMPLE_ITEMS)

  result = dataset.select_rows()

  def _get_rows() -> list[Item]:
    nonlocal result
    rows: list[Item] = []
    for r in result:
      rows.append(r)
    return rows

  # Make sure we can iterate twice.
  assert _get_rows() == SIMPLE_ITEMS
  assert _get_rows() == SIMPLE_ITEMS


def test_select_rows_next(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data(SIMPLE_ITEMS)

  result = dataset.select_rows()

  def _get_rows() -> list[Item]:
    nonlocal result
    rows: list[Item] = []
    while True:
      try:
        rows.append(next(result))
      except StopIteration:
        break

    return rows

  # Make sure we can iterate with next() twice.
  assert _get_rows() == SIMPLE_ITEMS
  assert _get_rows() == SIMPLE_ITEMS


def test_merge_values(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data([{'text': 'hello'}, {'text': 'everybody'}])
  test_signal = TestSignal()
  dataset.compute_signal(test_signal, 'text')
  length_signal = LengthSignal()
  dataset.compute_signal(length_signal, 'text')

  result = dataset.select_rows(['text'], combine_columns=True)
  assert list(result) == [
    {'text': enriched_item('hello', {'length_signal': 5, 'test_signal': {'len': 5, 'flen': 5.0}})},
    {
      'text': enriched_item(
        'everybody', {'length_signal': 9, 'test_signal': {'len': 9, 'flen': 9.0}}
      )
    },
  ]

  # Test subselection.
  result = dataset.select_rows(
    ['text', ('text', 'test_signal', 'flen'), ('text', 'test_signal', 'len')]
  )
  assert list(result) == [
    {'text': 'hello', 'text.test_signal.flen': 5.0, 'text.test_signal.len': 5},
    {'text': 'everybody', 'text.test_signal.flen': 9.0, 'text.test_signal.len': 9},
  ]

  # Test subselection with combine_columns=True.
  result = dataset.select_rows(
    ['text', ('text', 'test_signal', 'flen'), ('text', 'test_signal', 'len')], combine_columns=True
  )
  assert list(result) == [
    {'text': enriched_item('hello', {'length_signal': 5, 'test_signal': {'len': 5, 'flen': 5.0}})},
    {
      'text': enriched_item(
        'everybody', {'length_signal': 9, 'test_signal': {'len': 9, 'flen': 9.0}}
      )
    },
  ]

  # Test subselection with aliasing.
  result = dataset.select_rows(
    columns=['text', Column(('text', 'test_signal', 'len'), alias='metadata')]
  )
  assert list(result) == [{'text': 'hello', 'metadata': 5}, {'text': 'everybody', 'metadata': 9}]

  result = dataset.select_rows(columns=['text'], combine_columns=True)
  assert list(result) == [
    {'text': enriched_item('hello', {'length_signal': 5, 'test_signal': {'len': 5, 'flen': 5.0}})},
    {
      'text': enriched_item(
        'everybody', {'length_signal': 9, 'test_signal': {'len': 9, 'flen': 9.0}}
      )
    },
  ]


def test_enriched_select_all(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data([{'text': 'hello'}, {'text': 'everybody'}])
  test_signal = TestSignal()
  dataset.compute_signal(test_signal, 'text')
  length_signal = LengthSignal()
  dataset.compute_signal(length_signal, 'text')

  result = dataset.select_rows()
  assert list(result) == [
    {
      'text': 'hello',
      'text.length_signal': 5,
      'text.test_signal.len': 5,
      'text.test_signal.flen': 5.0,
    },
    {
      'text': 'everybody',
      'text.length_signal': 9,
      'text.test_signal.len': 9,
      'text.test_signal.flen': 9.0,
    },
  ]


def test_merge_array_values(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data([{'texts': ['hello', 'everybody']}, {'texts': ['a', 'bc', 'def']}])

  test_signal = TestSignal()
  dataset.compute_signal(test_signal, ('texts', '*'))
  length_signal = LengthSignal()
  dataset.compute_signal(length_signal, ('texts', '*'))

  assert dataset.manifest() == DatasetManifest(
    namespace=TEST_NAMESPACE,
    dataset_name=TEST_DATASET_NAME,
    data_schema=schema(
      {
        'texts': [
          field(
            'string',
            fields={
              'length_signal': field('int32', length_signal.model_dump()),
              'test_signal': field(
                signal=test_signal.model_dump(), fields={'len': 'int32', 'flen': 'float32'}
              ),
            },
          )
        ]
      }
    ),
    num_items=2,
    source=TestSource(),
  )

  result = dataset.select_rows(['texts'], combine_columns=True)
  assert list(result) == [
    {
      'texts': [
        enriched_item('hello', {'length_signal': 5, 'test_signal': {'len': 5, 'flen': 5.0}}),
        enriched_item('everybody', {'length_signal': 9, 'test_signal': {'len': 9, 'flen': 9.0}}),
      ]
    },
    {
      'texts': [
        enriched_item('a', {'length_signal': 1, 'test_signal': {'len': 1, 'flen': 1.0}}),
        enriched_item('bc', {'length_signal': 2, 'test_signal': {'len': 2, 'flen': 2.0}}),
        enriched_item('def', {'length_signal': 3, 'test_signal': {'len': 3, 'flen': 3.0}}),
      ]
    },
  ]

  # Test subselection.
  result = dataset.select_rows(
    [('texts', '*'), ('texts', '*', 'length_signal'), ('texts', '*', 'test_signal', 'flen')]
  )
  assert list(result) == [
    {
      'texts.*': ['hello', 'everybody'],
      'texts.*.test_signal.flen': [5.0, 9.0],
      'texts.*.length_signal': [5, 9],
    },
    {
      'texts.*': ['a', 'bc', 'def'],
      'texts.*.test_signal.flen': [1.0, 2.0, 3.0],
      'texts.*.length_signal': [1, 2, 3],
    },
  ]


def test_combining_columns(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data(
    [
      {
        'text': 'hello',
        'extra': {'text': {'length_signal': 5, 'test_signal': {'len': 5, 'flen': 5.0}}},
      },
      {
        'text': 'everybody',
        'extra': {'text': {'length_signal': 9, 'test_signal': {'len': 9, 'flen': 9.0}}},
      },
    ]
  )

  # Sub-select text and test_signal.
  result = dataset.select_rows(['text', ('extra', 'text', 'test_signal')], combine_columns=True)
  assert list(result) == [
    {'text': 'hello', 'extra': {'text': {'test_signal': {'len': 5, 'flen': 5.0}}}},
    {'text': 'everybody', 'extra': {'text': {'test_signal': {'len': 9, 'flen': 9.0}}}},
  ]

  # Sub-select text and length_signal.
  result = dataset.select_rows(['text', ('extra', 'text', 'length_signal')], combine_columns=True)
  assert list(result) == [
    {'text': 'hello', 'extra': {'text': {'length_signal': 5}}},
    {'text': 'everybody', 'extra': {'text': {'length_signal': 9}}},
  ]

  # Sub-select length_signal only.
  result = dataset.select_rows([('extra', 'text', 'length_signal')], combine_columns=True)
  assert list(result) == [
    {'extra': {'text': {'length_signal': 5}}},
    {'extra': {'text': {'length_signal': 9}}},
  ]

  # Aliases are ignored when combing columns.
  len_col = Column(('extra', 'text', 'length_signal'), alias='hello')
  result = dataset.select_rows([len_col], combine_columns=True)
  assert list(result) == [
    {'extra': {'text': {'length_signal': 5}}},
    {'extra': {'text': {'length_signal': 9}}},
  ]

  # Works with UDFs and aliases are ignored.
  udf_col = Column('text', alias='ignored', signal_udf=LengthSignal())
  result = dataset.select_rows(['text', udf_col], combine_columns=True)
  assert list(result) == [
    {'text': enriched_item('hello', {'length_signal': 5})},
    {'text': enriched_item('everybody', {'length_signal': 9})},
  ]


def test_source_joined_with_named_signal(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data(SIMPLE_ITEMS)
  assert dataset.manifest() == DatasetManifest(
    namespace=TEST_NAMESPACE,
    dataset_name=TEST_DATASET_NAME,
    data_schema=schema({'str': 'string', 'int': 'int32', 'bool': 'boolean', 'float': 'float32'}),
    num_items=3,
    source=TestSource(),
  )

  test_signal = TestSignal()
  dataset.compute_signal(test_signal, 'str')

  # Check the enriched dataset manifest has 'text' enriched.
  assert dataset.manifest() == DatasetManifest(
    namespace=TEST_NAMESPACE,
    dataset_name=TEST_DATASET_NAME,
    data_schema=schema(
      {
        'str': field(
          'string',
          fields={
            'test_signal': field(
              signal=test_signal.model_dump(), fields={'len': 'int32', 'flen': 'float32'}
            )
          },
        ),
        'int': 'int32',
        'bool': 'boolean',
        'float': 'float32',
      }
    ),
    num_items=3,
    source=TestSource(),
  )

  result = dataset.select_rows(['str', Column(('str', 'test_signal'), alias='test_signal_on_str')])

  assert list(result) == [
    {'str': 'a', 'test_signal_on_str': {'len': 1, 'flen': 1.0}},
    {'str': 'b', 'test_signal_on_str': {'len': 1, 'flen': 1.0}},
    {'str': 'b', 'test_signal_on_str': {'len': 1, 'flen': 1.0}},
  ]


def test_invalid_column_paths(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data(
    [
      {
        'text': enriched_item('hello', {'test_signal': {'len': 5}}),
        'text2': [
          enriched_item('hello', {'test_signal': {'len': 5}}),
          enriched_item('hi', {'test_signal': {'len': 2}}),
        ],
      }
    ]
  )

  with pytest.raises(ValueError, match='Path part "invalid" not found in the dataset'):
    dataset.select_rows([('text', 'test_signal', 'invalid')])

  with pytest.raises(ValueError, match='Selecting a specific index of a repeated field'):
    dataset.select_rows([('text2', '4', 'test_signal')])


def test_signal_with_quote(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data([{'text': 'hello'}, {'text': 'world'}])
  dataset.compute_signal(SignalWithQuoteInIt(), 'text')
  dataset.compute_signal(SignalWithDoubleQuoteInIt(), 'text')
  result = dataset.select_rows(['text'], combine_columns=True)
  assert list(result) == [
    {'text': enriched_item('hello', {"test'signal": True, 'test"signal': True})},
    {'text': enriched_item('world', {"test'signal": True, 'test"signal': True})},
  ]

  result = dataset.select_rows(
    ['text', "text.test'signal", 'text.test"signal'], combine_columns=False
  )
  assert list(result) == [
    {'text': 'hello', "text.test'signal": True, 'text.test"signal': True},
    {'text': 'world', "text.test'signal": True, 'text.test"signal': True},
  ]


class SignalWithQuoteInIt(TextSignal):
  name: ClassVar[str] = "test'signal"

  @override
  def fields(self) -> Field:
    return field('boolean')

  @override
  def compute(self, data: Iterable[RichData]) -> Iterable[Optional[Item]]:
    for d in data:
      yield True


class SignalWithDoubleQuoteInIt(TextSignal):
  name: ClassVar[str] = 'test"signal'

  @override
  def fields(self) -> Field:
    return field('boolean')

  @override
  def compute(self, data: Iterable[RichData]) -> Iterable[Optional[Item]]:
    for d in data:
      yield True


def test_dataset_config_from_manifest(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data([{'text': 'hello.'}, {'text': 'hello world.'}])
  dataset.compute_signal(TestSignal(), 'text')
  dataset.compute_embedding('test_embedding', 'text')

  assert dataset.manifest() == DatasetManifest(
    namespace=TEST_NAMESPACE,
    dataset_name=TEST_DATASET_NAME,
    data_schema=schema(
      {
        'text': field(
          'string',
          fields={
            'test_signal': field(
              signal=TestSignal().model_dump(), fields={'len': 'int32', 'flen': 'float32'}
            ),
            'test_embedding': field(
              signal=TestEmbedding().model_dump(),
              fields=[field('string_span', fields={EMBEDDING_KEY: 'embedding'})],
            ),
          },
        )
      }
    ),
    num_items=2,
    source=TestSource(),
  )

  config = dataset_config_from_manifest(dataset.manifest())

  assert config == DatasetConfig(
    namespace=TEST_NAMESPACE,
    name=TEST_DATASET_NAME,
    source=TestSource(),
    embeddings=[EmbeddingConfig(path=('text',), embedding='test_embedding')],
    signals=[SignalConfig(path=('text',), signal=TestSignal())],
  )


def test_map_dtype(make_test_data: TestDataMaker) -> None:
  items = [
    {'column': {'a': 1.0, 'b': 2.0}},
    {'column': {'b': 2.5}},
    {'column': {'a': 3.0, 'c': 3.5}},
  ]
  map_dtype = MapType(key_type='string', value_type='float32')
  data_schema = schema({'column': Field(dtype=map_dtype)})
  dataset = make_test_data(items, schema=data_schema)
  assert dataset.manifest() == DatasetManifest(
    namespace='test_namespace',
    dataset_name='test_dataset',
    data_schema=schema(
      {
        'column': Field(
          dtype=map_dtype,
          fields={'a': field('float32'), 'b': field('float32'), 'c': field('float32')},
        )
      }
    ),
    source=TestSource(),
    num_items=3,
  )

  result = dataset.select_rows(['column'])
  assert list(result) == [
    {'column': {'key': ['a', 'b'], 'value': [1.0, 2.0]}},
    {'column': {'key': ['b'], 'value': [2.5]}},
    {'column': {'key': ['a', 'c'], 'value': [3.0, 3.5]}},
  ]
