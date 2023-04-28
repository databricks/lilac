"""Implementation-agnostic tests of the Dataset DB API."""

import pathlib
import re
from typing import Any, Generator, Iterable, Optional, Type, cast

import numpy as np
import pandas as pd
import pytest
from pytest_mock import MockerFixture
from typing_extensions import override

from ..config import CONFIG
from ..embeddings.embedding_index import EmbeddingIndexerManifest, EmbeddingIndexInfo
from ..embeddings.embedding_registry import (
    Embedding,
    clear_embedding_registry,
    register_embedding,
)
from ..embeddings.vector_store import VectorStore
from ..schema import (
    PATH_WILDCARD,
    TEXT_SPAN_END_FEATURE,
    TEXT_SPAN_START_FEATURE,
    UUID_COLUMN,
    DataType,
    EnrichmentType,
    Entity,
    EntityField,
    Field,
    Item,
    ItemValue,
    RichData,
    Schema,
    SignalOut,
    TextSpan,
)
from ..signals.signal import Signal
from ..signals.signal_registry import clear_signal_registry, register_signal
from . import db_dataset, db_dataset_duckdb
from .db_dataset import (
    Column,
    Comparison,
    DatasetDB,
    DatasetManifest,
    EntityIndex,
    FilterTuple,
    NamedBins,
    SignalUDF,
    SortOrder,
    StatsResult,
)
from .db_dataset_duckdb import DatasetDuckDB
from .db_dataset_test_utils import TEST_DATASET_NAME, TEST_NAMESPACE, make_db

ALL_DBS = [DatasetDuckDB]

SIMPLE_DATASET_NAME = 'simple'

SIMPLE_ITEMS: list[Item] = [{
    UUID_COLUMN: '1',
    'str': 'a',
    'int': 1,
    'bool': False,
    'float': 3.0
}, {
    UUID_COLUMN: '2',
    'str': 'b',
    'int': 2,
    'bool': True,
    'float': 2.0
}, {
    UUID_COLUMN: '2',
    'str': 'b',
    'int': 2,
    'bool': True,
    'float': 1.0
}]

SIMPLE_SCHEMA = Schema(
    fields={
        UUID_COLUMN: Field(dtype=DataType.STRING),
        'str': Field(dtype=DataType.STRING),
        'int': Field(dtype=DataType.INT64),
        'bool': Field(dtype=DataType.BOOLEAN),
        'float': Field(dtype=DataType.FLOAT64),
    })

TEST_EMBEDDING_NAME = 'test_embedding'

EMBEDDINGS: list[tuple[str, list[float]]] = [('hello.', [1.0, 0.0, 0.0]),
                                             ('hello2.', [1.0, 1.0, 0.0]),
                                             ('hello world.', [1.0, 1.0, 1.0]),
                                             ('hello world2.', [2.0, 1.0, 1.0])]

STR_EMBEDDINGS: dict[str, list[float]] = {text: embedding for text, embedding in EMBEDDINGS}


class TestEmbedding(Embedding):
  """A test embed function."""
  name = TEST_EMBEDDING_NAME
  enrichment_type = EnrichmentType.TEXT

  @override
  def __call__(self, data: Iterable[RichData]) -> np.ndarray:
    """Embed the examples, use a hashmap to the vector for simplicity."""
    return np.array([STR_EMBEDDINGS[cast(str, example)] for example in data])


@pytest.fixture(scope='module', autouse=True)
def setup_teardown() -> Iterable[None]:
  # Setup.
  register_signal(TestSignal)
  register_signal(TestSplitterWithLen)
  register_signal(TestEmbeddingSumSignal)
  register_signal(TestEntitySignal)
  register_embedding(TestEmbedding)

  # Unit test runs.
  yield

  # Teardown.
  clear_signal_registry()
  clear_embedding_registry()


@pytest.fixture(autouse=True)
def set_data_path(tmp_path: pathlib.Path) -> Generator:
  data_path = CONFIG['LILAC_DATA_PATH']
  CONFIG['LILAC_DATA_PATH'] = str(tmp_path)

  yield

  CONFIG['LILAC_DATA_PATH'] = data_path or ''


@pytest.mark.parametrize('db_cls', ALL_DBS)
class SelectRowsSuite:

  def test_default(self, tmp_path: pathlib.Path, db_cls: Type[DatasetDB]) -> None:
    db = make_db(db_cls, tmp_path, SIMPLE_ITEMS, SIMPLE_SCHEMA)

    result = db.select_rows()
    assert list(result) == SIMPLE_ITEMS

  def test_select_ids(self, tmp_path: pathlib.Path, db_cls: Type[DatasetDB]) -> None:
    db = make_db(db_cls, tmp_path, SIMPLE_ITEMS, SIMPLE_SCHEMA)

    result = db.select_rows([UUID_COLUMN])

    assert list(result) == [{UUID_COLUMN: '1'}, {UUID_COLUMN: '2'}, {UUID_COLUMN: '2'}]

  def test_select_ids_with_limit_and_offset(self, tmp_path: pathlib.Path,
                                            db_cls: Type[DatasetDB]) -> None:
    items: list[Item] = [{UUID_COLUMN: str(i)} for i in range(10, 20)]
    db = make_db(db_cls, tmp_path, items, SIMPLE_SCHEMA)

    result = db.select_rows([UUID_COLUMN], offset=1, limit=3)
    assert list(result) == [{UUID_COLUMN: '11'}, {UUID_COLUMN: '12'}, {UUID_COLUMN: '13'}]

    result = db.select_rows([UUID_COLUMN], offset=7, limit=2)
    assert list(result) == [{UUID_COLUMN: '17'}, {UUID_COLUMN: '18'}]

    result = db.select_rows([UUID_COLUMN], offset=9, limit=200)
    assert list(result) == [{UUID_COLUMN: '19'}]

    result = db.select_rows([UUID_COLUMN], offset=10, limit=200)
    assert list(result) == []

  def test_filter_by_ids(self, tmp_path: pathlib.Path, db_cls: Type[DatasetDB]) -> None:
    db = make_db(db_cls, tmp_path, SIMPLE_ITEMS, SIMPLE_SCHEMA)

    id_filter: FilterTuple = (UUID_COLUMN, Comparison.EQUALS, '1')
    result = db.select_rows(filters=[id_filter])

    assert list(result) == [{UUID_COLUMN: '1', 'str': 'a', 'int': 1, 'bool': False, 'float': 3.0}]

    id_filter = (UUID_COLUMN, Comparison.EQUALS, '2')
    result = db.select_rows(filters=[id_filter])

    assert list(result) == [{
        UUID_COLUMN: '2',
        'str': 'b',
        'int': 2,
        'bool': True,
        'float': 2.0
    }, {
        UUID_COLUMN: '2',
        'str': 'b',
        'int': 2,
        'bool': True,
        'float': 1.0
    }]

    id_filter = (UUID_COLUMN, Comparison.EQUALS, b'f')
    result = db.select_rows(filters=[id_filter])

    assert list(result) == []

  def test_columns(self, tmp_path: pathlib.Path, db_cls: Type[DatasetDB]) -> None:
    db = make_db(db_cls, tmp_path, SIMPLE_ITEMS, SIMPLE_SCHEMA)

    result = db.select_rows(columns=['str', 'float'])

    assert list(result) == [{
        UUID_COLUMN: '1',
        'str': 'a',
        'float': 3.0
    }, {
        UUID_COLUMN: '2',
        'str': 'b',
        'float': 2.0
    }, {
        UUID_COLUMN: '2',
        'str': 'b',
        'float': 1.0
    }]

  def test_source_joined_with_signal_column(self, tmp_path: pathlib.Path,
                                            db_cls: Type[DatasetDB]) -> None:
    db = make_db(db_cls, tmp_path, SIMPLE_ITEMS, SIMPLE_SCHEMA)
    assert db.manifest() == DatasetManifest(namespace=TEST_NAMESPACE,
                                            dataset_name=TEST_DATASET_NAME,
                                            data_schema=Schema(
                                                fields={
                                                    UUID_COLUMN: Field(dtype=DataType.STRING),
                                                    'str': Field(dtype=DataType.STRING),
                                                    'int': Field(dtype=DataType.INT64),
                                                    'bool': Field(dtype=DataType.BOOLEAN),
                                                    'float': Field(dtype=DataType.FLOAT64),
                                                }),
                                            embedding_manifest=EmbeddingIndexerManifest(indexes=[]),
                                            entity_indexes=[],
                                            num_items=3)

    test_signal = TestSignal()
    db.compute_signal_column(signal=test_signal, column='str')

    result = db.select_rows(columns=['str', 'test_signal(str)'])

    assert list(result) == [{
        UUID_COLUMN: '1',
        'str': 'a',
        'test_signal(str)': {
            'len': 1,
            'flen': 1.0
        }
    }, {
        UUID_COLUMN: '2',
        'str': 'b',
        'test_signal(str)': {
            'len': 1,
            'flen': 1.0
        }
    }, {
        UUID_COLUMN: '2',
        'str': 'b',
        'test_signal(str)': {
            'len': 1,
            'flen': 1.0
        }
    }]

    # Check the enriched dataset manifest has 'text' enriched.
    assert db.manifest() == DatasetManifest(
        namespace=TEST_NAMESPACE,
        dataset_name=TEST_DATASET_NAME,
        data_schema=Schema(
            fields={
                UUID_COLUMN: Field(dtype=DataType.STRING),
                'str': Field(dtype=DataType.STRING),
                'int': Field(dtype=DataType.INT64),
                'bool': Field(dtype=DataType.BOOLEAN),
                'float': Field(dtype=DataType.FLOAT64),
                'test_signal(str)': Field(fields={
                    'len': Field(dtype=DataType.INT32, derived_from=('str',)),
                    'flen': Field(dtype=DataType.FLOAT32, derived_from=('str',))
                },
                                          derived_from=('str',))
            }),
        embedding_manifest=EmbeddingIndexerManifest(indexes=[]),
        entity_indexes=[],
        num_items=3)

    # Select a specific signal leaf test_signal.flen.
    result = db.select_rows(columns=['str', ('test_signal(str)', 'flen')])

    assert list(result) == [{
        UUID_COLUMN: '1',
        'str': 'a',
        'test_signal(str).flen': 1.0
    }, {
        UUID_COLUMN: '2',
        'str': 'b',
        'test_signal(str).flen': 1.0
    }, {
        UUID_COLUMN: '2',
        'str': 'b',
        'test_signal(str).flen': 1.0
    }]

    # Select multiple signal leafs with aliasing.
    result = db.select_rows(columns=[
        'str',
        Column(('test_signal(str)', 'flen'), alias='flen'),
        Column(('test_signal(str)', 'len'), alias='len')
    ])

    assert list(result) == [{
        UUID_COLUMN: '1',
        'str': 'a',
        'flen': 1.0,
        'len': 1
    }, {
        UUID_COLUMN: '2',
        'str': 'b',
        'flen': 1.0,
        'len': 1
    }, {
        UUID_COLUMN: '2',
        'str': 'b',
        'flen': 1.0,
        'len': 1
    }]

  def test_signal_on_repeated_field(self, tmp_path: pathlib.Path, db_cls: Type[DatasetDB]) -> None:
    db = make_db(db_cls,
                 tmp_path,
                 items=[{
                     UUID_COLUMN: '1',
                     'text': ['hello', 'everybody'],
                 }, {
                     UUID_COLUMN: '2',
                     'text': ['hello2', 'everybody2'],
                 }],
                 schema=Schema(
                     fields={
                         UUID_COLUMN: Field(dtype=DataType.STRING),
                         'text': Field(repeated_field=Field(dtype=DataType.STRING)),
                     }))
    test_signal = TestSignal()
    # Run the signal on the repeated field.
    db.compute_signal_column(signal=test_signal, column=('text', '*'))

    # Check the enriched dataset manifest has 'text' enriched.
    assert db.manifest() == DatasetManifest(
        namespace=TEST_NAMESPACE,
        dataset_name=TEST_DATASET_NAME,
        data_schema=Schema(
            fields={
                UUID_COLUMN: Field(dtype=DataType.STRING),
                'text': Field(repeated_field=Field(dtype=DataType.STRING)),
                'test_signal(text)': Field(repeated_field=Field(fields={
                    'len': Field(dtype=DataType.INT32, derived_from=('text', '*')),
                    'flen': Field(dtype=DataType.FLOAT32, derived_from=('text', '*'))
                },
                                                                derived_from=('text', '*')),
                                           derived_from=('text', '*'))
            }),
        embedding_manifest=EmbeddingIndexerManifest(indexes=[]),
        entity_indexes=[],
        num_items=2)

    result = db.select_rows(columns=[('test_signal(text)')])

    assert list(result) == [{
        UUID_COLUMN: '1',
        'test_signal(text)': [{
            'len': 5,
            'flen': 5.0
        }, {
            'len': 9,
            'flen': 9.0
        }]
    }, {
        UUID_COLUMN: '2',
        'test_signal(text)': [{
            'len': 6,
            'flen': 6.0
        }, {
            'len': 10,
            'flen': 10.0
        }]
    }]

  def test_signal_transform(self, tmp_path: pathlib.Path, db_cls: Type[DatasetDB]) -> None:
    db = make_db(db_cls,
                 tmp_path,
                 items=[{
                     UUID_COLUMN: '1',
                     'text': 'hello'
                 }, {
                     UUID_COLUMN: '2',
                     'text': 'everybody'
                 }],
                 schema=Schema(fields={
                     UUID_COLUMN: Field(dtype=DataType.STRING),
                     'text': Field(dtype=DataType.STRING),
                 }))

    signal_col = SignalUDF(TestSignal(), 'text')
    result = db.select_rows(columns=['text', signal_col])

    assert list(result) == [{
        UUID_COLUMN: '1',
        'text': 'hello',
        'test_signal(text)': {
            'len': 5,
            'flen': 5.0
        }
    }, {
        UUID_COLUMN: '2',
        'text': 'everybody',
        'test_signal(text)': {
            'len': 9,
            'flen': 9.0
        }
    }]

  def test_signal_transform_with_filters(self, tmp_path: pathlib.Path,
                                         db_cls: Type[DatasetDB]) -> None:
    db = make_db(db_cls,
                 tmp_path,
                 items=[{
                     UUID_COLUMN: '1',
                     'text': 'hello'
                 }, {
                     UUID_COLUMN: '2',
                     'text': 'everybody'
                 }],
                 schema=Schema(fields={
                     UUID_COLUMN: Field(dtype=DataType.STRING),
                     'text': Field(dtype=DataType.STRING),
                 }))

    signal_col = SignalUDF(TestSignal(), 'text')
    # Filter by source feature.
    filters: list[FilterTuple] = [('text', Comparison.EQUALS, 'everybody')]
    result = db.select_rows(columns=['text', signal_col], filters=filters)
    assert list(result) == [{
        UUID_COLUMN: '2',
        'text': 'everybody',
        'test_signal(text)': {
            'len': 9,
            'flen': 9.0
        }
    }]

    # Filter by transformed feature.
    filters = [(('test_signal(text)', 'len'), Comparison.LESS, 7)]
    result = db.select_rows(columns=['text', signal_col], filters=filters)

    assert list(result) == [{
        UUID_COLUMN: '1',
        'text': 'hello',
        'test_signal(text)': {
            'len': 5,
            'flen': 5.0
        }
    }]

    filters = [(('test_signal(text)', 'flen'), Comparison.GREATER, 6.0)]
    result = db.select_rows(columns=['text', signal_col], filters=filters)

    assert list(result) == [{
        UUID_COLUMN: '2',
        'text': 'everybody',
        'test_signal(text)': {
            'len': 9,
            'flen': 9.0
        }
    }]

  class LengthSignal(Signal):
    name = 'length_signal'
    enrichment_type = EnrichmentType.TEXT
    vector_based = False

    call_count: int = 0

    def fields(self) -> Field:
      return Field(dtype=DataType.INT32)

    def compute(self, data: Iterable[RichData]) -> Iterable[Optional[SignalOut]]:
      for text_content in data:
        self.call_count += 1
        yield len(text_content)

  def test_signal_transform_with_uuid_filter(self, tmp_path: pathlib.Path,
                                             db_cls: Type[DatasetDB]) -> None:

    db = make_db(db_cls,
                 tmp_path,
                 items=[{
                     UUID_COLUMN: '1',
                     'text': 'hello'
                 }, {
                     UUID_COLUMN: '2',
                     'text': 'everybody'
                 }],
                 schema=Schema(fields={
                     UUID_COLUMN: Field(dtype=DataType.STRING),
                     'text': Field(dtype=DataType.STRING),
                 }))

    signal = SelectRowsSuite.LengthSignal()
    # Filter by a specific UUID.
    filters: list[FilterTuple] = [(UUID_COLUMN, Comparison.EQUALS, '1')]
    result = db.select_rows(columns=['text', SignalUDF(signal, 'text')], filters=filters)
    assert list(result) == [{UUID_COLUMN: '1', 'text': 'hello', 'length_signal(text)': 5}]
    assert signal.call_count == 1

    filters = [(UUID_COLUMN, Comparison.EQUALS, '2')]
    result = db.select_rows(columns=['text', SignalUDF(signal, 'text')], filters=filters)
    assert list(result) == [{UUID_COLUMN: '2', 'text': 'everybody', 'length_signal(text)': 9}]
    assert signal.call_count == 1 + 1

    # No filters.
    result = db.select_rows(columns=['text', SignalUDF(signal, 'text')])
    assert list(result) == [{
        UUID_COLUMN: '1',
        'text': 'hello',
        'length_signal(text)': 5
    }, {
        UUID_COLUMN: '2',
        'text': 'everybody',
        'length_signal(text)': 9
    }]
    assert signal.call_count == 2 + 2

  def test_signal_transform_with_uuid_filter_repeated(self, tmp_path: pathlib.Path,
                                                      db_cls: Type[DatasetDB]) -> None:

    db = make_db(db_cls,
                 tmp_path,
                 items=[{
                     UUID_COLUMN: '1',
                     'text': ['hello', 'hi']
                 }, {
                     UUID_COLUMN: '2',
                     'text': ['everybody', 'bye', 'test']
                 }],
                 schema=Schema(
                     fields={
                         UUID_COLUMN: Field(dtype=DataType.STRING),
                         'text': Field(repeated_field=Field(dtype=DataType.STRING)),
                     }))

    signal = SelectRowsSuite.LengthSignal()

    # Filter by a specific UUID.
    filters: list[FilterTuple] = [(UUID_COLUMN, Comparison.EQUALS, '1')]
    result = db.select_rows(columns=['text', SignalUDF(signal, ('text', '*'))], filters=filters)
    assert list(result) == [{
        UUID_COLUMN: '1',
        'text': ['hello', 'hi'],
        'length_signal(text)': [5, 2]
    }]
    assert signal.call_count == 2

    # Filter by a specific UUID.
    filters = [(UUID_COLUMN, Comparison.EQUALS, '2')]
    result = db.select_rows(columns=['text', SignalUDF(signal, ('text', '*'))], filters=filters)
    assert list(result) == [{
        UUID_COLUMN: '2',
        'text': ['everybody', 'bye', 'test'],
        'length_signal(text)': [9, 3, 4]
    }]
    assert signal.call_count == 2 + 3

  def test_signal_transform_deeply_nested(self, tmp_path: pathlib.Path,
                                          db_cls: Type[DatasetDB]) -> None:

    db = make_db(
        db_cls,
        tmp_path,
        items=[{
            UUID_COLUMN: '1',
            'text': [['hello'], ['hi', 'bye']]
        }, {
            UUID_COLUMN: '2',
            'text': [['everybody', 'bye'], ['test']]
        }],
        schema=Schema(
            fields={
                UUID_COLUMN: Field(dtype=DataType.STRING),
                'text': Field(repeated_field=Field(repeated_field=Field(dtype=DataType.STRING))),
            }))

    signal = SelectRowsSuite.LengthSignal()

    result = db.select_rows(columns=[SignalUDF(signal, ('text', '*', '*'))])
    assert list(result) == [{
        UUID_COLUMN: '1',
        'length_signal(text_*)': [[5], [2, 3]]
    }, {
        UUID_COLUMN: '2',
        'length_signal(text_*)': [[9, 3], [4]]
    }]
    assert signal.call_count == 6

  def test_signal_transform_with_embedding(self, tmp_path: pathlib.Path,
                                           db_cls: Type[DatasetDB]) -> None:
    db = make_db(db_cls=db_cls,
                 tmp_path=tmp_path,
                 items=[{
                     UUID_COLUMN: '1',
                     'text': 'hello.',
                 }, {
                     UUID_COLUMN: '2',
                     'text': 'hello2.',
                 }],
                 schema=Schema(fields={
                     UUID_COLUMN: Field(dtype=DataType.STRING),
                     'text': Field(dtype=DataType.STRING),
                 }))

    db.compute_embedding_index(embedding=TEST_EMBEDDING_NAME, column='text')

    signal_col = SignalUDF(TestEmbeddingSumSignal(embedding=TEST_EMBEDDING_NAME), column='text')
    result = db.select_rows(columns=['text', signal_col])
    expected_result = [{
        UUID_COLUMN: '1',
        'text': 'hello.',
        'test_embedding_sum(text)': 1.0
    }, {
        UUID_COLUMN: '2',
        'text': 'hello2.',
        'test_embedding_sum(text)': 2.0
    }]
    assert list(result) == expected_result

    # Select rows with alias.
    signal_col = SignalUDF(TestEmbeddingSumSignal(embedding=TEST_EMBEDDING_NAME),
                           Column('text'),
                           alias='emb_sum')
    result = db.select_rows(columns=['text', signal_col])
    expected_result = [{
        UUID_COLUMN: '1',
        'text': 'hello.',
        'emb_sum': 1.0
    }, {
        UUID_COLUMN: '2',
        'text': 'hello2.',
        'emb_sum': 2.0
    }]
    assert list(result) == expected_result

  def test_signal_transform_with_nested_embedding(self, tmp_path: pathlib.Path,
                                                  db_cls: Type[DatasetDB]) -> None:
    db = make_db(db_cls=db_cls,
                 tmp_path=tmp_path,
                 items=[{
                     UUID_COLUMN: '1',
                     'text': ['hello.', 'hello world.'],
                 }, {
                     UUID_COLUMN: '2',
                     'text': ['hello world2.', 'hello2.'],
                 }],
                 schema=Schema(
                     fields={
                         UUID_COLUMN: Field(dtype=DataType.STRING),
                         'text': Field(repeated_field=Field(dtype=DataType.STRING)),
                     }))

    db.compute_embedding_index(embedding=TEST_EMBEDDING_NAME, column=('text', '*'))

    signal_col = SignalUDF(TestEmbeddingSumSignal(embedding=TEST_EMBEDDING_NAME),
                           column=('text', '*'))
    result = db.select_rows(columns=['text', signal_col])
    expected_result = [{
        UUID_COLUMN: '1',
        'text': ['hello.', 'hello world.'],
        'test_embedding_sum(text)': [1.0, 3.0]
    }, {
        UUID_COLUMN: '2',
        'text': ['hello world2.', 'hello2.'],
        'test_embedding_sum(text)': [4.0, 2.0]
    }]
    assert list(result) == expected_result

  def test_source_joined_with_named_signal_column(self, tmp_path: pathlib.Path,
                                                  db_cls: Type[DatasetDB]) -> None:
    db = make_db(db_cls, tmp_path, SIMPLE_ITEMS, SIMPLE_SCHEMA)
    assert db.manifest() == DatasetManifest(namespace=TEST_NAMESPACE,
                                            dataset_name=TEST_DATASET_NAME,
                                            data_schema=Schema(
                                                fields={
                                                    UUID_COLUMN: Field(dtype=DataType.STRING),
                                                    'str': Field(dtype=DataType.STRING),
                                                    'int': Field(dtype=DataType.INT64),
                                                    'bool': Field(dtype=DataType.BOOLEAN),
                                                    'float': Field(dtype=DataType.FLOAT64),
                                                }),
                                            embedding_manifest=EmbeddingIndexerManifest(indexes=[]),
                                            entity_indexes=[],
                                            num_items=3)

    test_signal = TestSignal()
    db.compute_signal_column(signal=test_signal,
                             column='str',
                             signal_column_name='test_signal_on_str')

    result = db.select_rows(columns=['str', 'test_signal_on_str'])

    assert list(result) == [{
        UUID_COLUMN: '1',
        'str': 'a',
        'test_signal_on_str': {
            'len': 1,
            'flen': 1.0
        }
    }, {
        UUID_COLUMN: '2',
        'str': 'b',
        'test_signal_on_str': {
            'len': 1,
            'flen': 1.0
        }
    }, {
        UUID_COLUMN: '2',
        'str': 'b',
        'test_signal_on_str': {
            'len': 1,
            'flen': 1.0
        }
    }]

    # Check the enriched dataset manifest has 'text' enriched.
    assert db.manifest() == DatasetManifest(
        namespace=TEST_NAMESPACE,
        dataset_name=TEST_DATASET_NAME,
        data_schema=Schema(
            fields={
                UUID_COLUMN: Field(dtype=DataType.STRING),
                'str': Field(dtype=DataType.STRING),
                'int': Field(dtype=DataType.INT64),
                'bool': Field(dtype=DataType.BOOLEAN),
                'float': Field(dtype=DataType.FLOAT64),
                'test_signal_on_str': Field(fields={
                    'len': Field(dtype=DataType.INT32, derived_from=('str',)),
                    'flen': Field(dtype=DataType.FLOAT32, derived_from=('str',))
                },
                                            derived_from=('str',))
            }),
        embedding_manifest=EmbeddingIndexerManifest(indexes=[]),
        entity_indexes=[],
        num_items=3)

  def test_text_splitter(self, tmp_path: pathlib.Path, db_cls: Type[DatasetDB]) -> None:
    db = make_db(db_cls=db_cls,
                 tmp_path=tmp_path,
                 items=[{
                     UUID_COLUMN: '1',
                     'text': '[1, 1] first sentence. [1, 1] second sentence.',
                 }, {
                     UUID_COLUMN: '2',
                     'text': 'b2 [2, 1] first sentence. [2, 1] second sentence.',
                 }],
                 schema=Schema(fields={
                     UUID_COLUMN: Field(dtype=DataType.STRING),
                     'text': Field(dtype=DataType.STRING),
                 }))

    db.compute_signal_column(signal=TestSplitterWithLen(), column='text')

    result = db.select_rows(columns=['text', 'test_splitter_len(text)'])
    expected_result = [{
        UUID_COLUMN: '1',
        'text': '[1, 1] first sentence. [1, 1] second sentence.',
        'test_splitter_len(text)': [{
            'len': 22,
            'split': {
                TEXT_SPAN_START_FEATURE: 0,
                TEXT_SPAN_END_FEATURE: 22
            }
        }, {
            'len': 23,
            'split': {
                TEXT_SPAN_START_FEATURE: 23,
                TEXT_SPAN_END_FEATURE: 46
            }
        }]
    }, {
        UUID_COLUMN: '2',
        'text': 'b2 [2, 1] first sentence. [2, 1] second sentence.',
        'test_splitter_len(text)': [{
            'len': 25,
            'split': {
                TEXT_SPAN_START_FEATURE: 0,
                TEXT_SPAN_END_FEATURE: 25
            }
        }, {
            'len': 23,
            'split': {
                TEXT_SPAN_START_FEATURE: 26,
                TEXT_SPAN_END_FEATURE: 49
            }
        }]
    }]
    assert list(result) == expected_result

  def test_entity_signal(self, tmp_path: pathlib.Path, db_cls: Type[DatasetDB]) -> None:
    db = make_db(db_cls=db_cls,
                 tmp_path=tmp_path,
                 items=[{
                     UUID_COLUMN: '1',
                     'text': '[1, 1] first sentence. [1, 1] second sentence.',
                 }, {
                     UUID_COLUMN: '2',
                     'text': 'b2 [2, 1] first sentence. [2, 1] second sentence.',
                 }],
                 schema=Schema(fields={
                     UUID_COLUMN: Field(dtype=DataType.STRING),
                     'text': Field(dtype=DataType.STRING),
                 }))

    signal = TestEntitySignal()
    db.compute_signal_column(signal=signal, column='text')

    assert db.manifest() == DatasetManifest(
        namespace=TEST_NAMESPACE,
        dataset_name=TEST_DATASET_NAME,
        data_schema=Schema(
            fields={
                UUID_COLUMN: Field(dtype=DataType.STRING),
                'text': Field(dtype=DataType.STRING),
                'test_entity_len(text)': Field(repeated_field=EntityField(
                    entity_value=Field(dtype=DataType.STRING_SPAN, derived_from=(('text',))),
                    fields={'len': Field(dtype=DataType.INT32, derived_from=('text',))}),
                                               derived_from=('text',))
            }),
        embedding_manifest=EmbeddingIndexerManifest(indexes=[]),
        entity_indexes=[
            EntityIndex(source_path=('text',),
                        index_path=('text', 'test_entity_len(text)'),
                        signal=signal)
        ],
        num_items=2)

    # NOTE: The way this currently works is it just generates a new signal column, in the old
    # format. This will look different once entity indexes are merged.
    result = db.select_rows(columns=['text', 'test_entity_len(text)'])
    expected_result = [{
        UUID_COLUMN: '1',
        'text': '[1, 1] first sentence. [1, 1] second sentence.',
        'test_entity_len(text)': [
            Entity(entity=TextSpan(0, 22), metadata={'len': 22}),
            Entity(entity=TextSpan(23, 46), metadata={'len': 23})
        ]
    }, {
        UUID_COLUMN: '2',
        'text': 'b2 [2, 1] first sentence. [2, 1] second sentence.',
        'test_entity_len(text)': [
            Entity(entity=TextSpan(0, 25), metadata={'len': 25}),
            Entity(entity=TextSpan(26, 49), metadata={'len': 23})
        ]
    }]
    assert list(result) == expected_result

  def test_embedding_signal(self, tmp_path: pathlib.Path, db_cls: Type[DatasetDB]) -> None:
    db = make_db(db_cls=db_cls,
                 tmp_path=tmp_path,
                 items=[{
                     UUID_COLUMN: '1',
                     'text': 'hello.',
                 }, {
                     UUID_COLUMN: '2',
                     'text': 'hello2.',
                 }],
                 schema=Schema(fields={
                     UUID_COLUMN: Field(dtype=DataType.STRING),
                     'text': Field(dtype=DataType.STRING),
                 }))

    embedding = TestEmbedding()
    db.compute_embedding_index(embedding=embedding, column='text')

    db.compute_signal_column(signal=TestEmbeddingSumSignal(embedding=TestEmbedding()),
                             column='text',
                             signal_column_name='text_emb_sum')

    assert db.manifest() == DatasetManifest(
        namespace=TEST_NAMESPACE,
        dataset_name=TEST_DATASET_NAME,
        data_schema=Schema(
            fields={
                UUID_COLUMN: Field(dtype=DataType.STRING),
                'text': Field(dtype=DataType.STRING),
                'text_emb_sum': Field(dtype=DataType.FLOAT32, derived_from=('text',))
            }),
        embedding_manifest=EmbeddingIndexerManifest(
            indexes=[EmbeddingIndexInfo(column=('text',), embedding=embedding)]),
        entity_indexes=[],
        num_items=2)

    result = db.select_rows(columns=['text', 'text_emb_sum'])
    expected_result = [{
        UUID_COLUMN: '1',
        'text': 'hello.',
        'text_emb_sum': 1.0
    }, {
        UUID_COLUMN: '2',
        'text': 'hello2.',
        'text_emb_sum': 2.0
    }]
    assert list(result) == expected_result

  def test_embedding_signal_splits(self, tmp_path: pathlib.Path, db_cls: Type[DatasetDB]) -> None:
    db = make_db(db_cls=db_cls,
                 tmp_path=tmp_path,
                 items=[{
                     UUID_COLUMN: '1',
                     'text': 'hello. hello2.',
                 }, {
                     UUID_COLUMN: '2',
                     'text': 'hello world. hello world2.',
                 }],
                 schema=Schema(fields={
                     UUID_COLUMN: Field(dtype=DataType.STRING),
                     'text': Field(dtype=DataType.STRING),
                 }))

    db.compute_signal_column(signal=TestSplitterWithLen(),
                             column='text',
                             signal_column_name='text_sentences')

    embedding = TestEmbedding()
    db.compute_embedding_index(embedding=embedding, column=('text_sentences', '*', 'split'))

    db.compute_signal_column(signal=TestEmbeddingSumSignal(embedding=TestEmbedding()),
                             column=('text_sentences', '*', 'split'),
                             signal_column_name='text_sentences_emb_sum')

    assert db.manifest() == DatasetManifest(
        namespace=TEST_NAMESPACE,
        dataset_name=TEST_DATASET_NAME,
        data_schema=Schema(
            fields={
                UUID_COLUMN: Field(dtype=DataType.STRING),
                'text': Field(dtype=DataType.STRING),
                'text_sentences_emb_sum': Field(repeated_field=Field(
                    fields={
                        'split': Field(dtype=DataType.FLOAT32,
                                       derived_from=('text_sentences', PATH_WILDCARD, 'split'))
                    })),
                'text_sentences': Field(repeated_field=Field(fields={
                    'len': Field(dtype=DataType.INT32, derived_from=('text',)),
                    'split': Field(dtype=DataType.STRING_SPAN, derived_from=('text',))
                },
                                                             derived_from=('text',)),
                                        derived_from=('text',))
            }),
        embedding_manifest=EmbeddingIndexerManifest(indexes=[
            EmbeddingIndexInfo(column=('text_sentences', '*', 'split'), embedding=embedding)
        ]),
        entity_indexes=[],
        num_items=2)

    result = db.select_rows(columns=['text', 'text_sentences', 'text_sentences_emb_sum'])
    expected_result = [{
        UUID_COLUMN: '1',
        'text': 'hello. hello2.',
        'text_sentences': [{
            'split': TextSpan(start=0, end=6),
            'len': 6
        }, {
            'split': TextSpan(start=7, end=14),
            'len': 7
        }],
        'text_sentences_emb_sum': [{
            'split': 1.0
        }, {
            'split': 2.0
        }]
    }, {
        UUID_COLUMN: '2',
        'text': 'hello world. hello world2.',
        'text_sentences': [{
            'split': TextSpan(start=0, end=12),
            'len': 12
        }, {
            'split': TextSpan(start=13, end=26),
            'len': 13
        }],
        'text_sentences_emb_sum': [{
            'split': 3.0
        }, {
            'split': 4.0
        }]
    }]
    assert list(result) == expected_result

  def test_invalid_column_paths(self, tmp_path: pathlib.Path, db_cls: Type[DatasetDB]) -> None:
    db = make_db(db_cls,
                 tmp_path,
                 items=[{
                     UUID_COLUMN: '1',
                     'text': 'hello',
                     'text2': ['hello', 'world'],
                 }, {
                     UUID_COLUMN: '2',
                     'text': 'hello world',
                     'text2': ['hello2', 'world2'],
                 }],
                 schema=Schema(
                     fields={
                         UUID_COLUMN: Field(dtype=DataType.STRING),
                         'text': Field(dtype=DataType.STRING),
                         'text2': Field(repeated_field=Field(dtype=DataType.STRING)),
                     }))
    test_signal = TestSignal()
    db.compute_signal_column(signal=test_signal, column='text')
    db.compute_signal_column(signal=test_signal, column=('text2', '*'))

    with pytest.raises(ValueError, match='Path part "invalid" not found in the dataset'):
      db.select_rows(columns=[('test_signal(text)', 'invalid')])

    with pytest.raises(ValueError, match='Selecting a specific index of a repeated field'):
      db.select_rows(columns=[('test_signal(text2)', 4)])

  def test_sort(self, tmp_path: pathlib.Path, db_cls: Type[DatasetDB]) -> None:
    db = make_db(db_cls, tmp_path, SIMPLE_ITEMS, SIMPLE_SCHEMA)

    result = db.select_rows(columns=[UUID_COLUMN, 'float'],
                            sort_by=['float'],
                            sort_order=SortOrder.ASC)

    assert list(result) == [{
        UUID_COLUMN: '2',
        'float': 1.0
    }, {
        UUID_COLUMN: '2',
        'float': 2.0
    }, {
        UUID_COLUMN: '1',
        'float': 3.0
    }]

    result = db.select_rows(columns=[UUID_COLUMN, 'float'],
                            sort_by=['float'],
                            sort_order=SortOrder.DESC)

    assert list(result) == [{
        UUID_COLUMN: '1',
        'float': 3.0
    }, {
        UUID_COLUMN: '2',
        'float': 2.0
    }, {
        UUID_COLUMN: '2',
        'float': 1.0
    }]

  def test_limit(self, tmp_path: pathlib.Path, db_cls: Type[DatasetDB]) -> None:
    db = make_db(db_cls, tmp_path, SIMPLE_ITEMS, SIMPLE_SCHEMA)

    result = db.select_rows(columns=[UUID_COLUMN, 'float'],
                            sort_by=['float'],
                            sort_order=SortOrder.ASC,
                            limit=2)
    assert list(result) == [{UUID_COLUMN: '2', 'float': 1.0}, {UUID_COLUMN: '2', 'float': 2.0}]


class TestSignal(Signal):
  name = 'test_signal'
  enrichment_type = EnrichmentType.TEXT
  vector_based = False

  @override
  def fields(self) -> Field:
    return Field(fields={'len': Field(dtype=DataType.INT32), 'flen': Field(dtype=DataType.FLOAT32)})

  @override
  def compute(self, data: Iterable[RichData]) -> Iterable[Optional[Item]]:
    return [{'len': len(text_content), 'flen': float(len(text_content))} for text_content in data]


class TestSplitterWithLen(Signal):
  """Split documents into sentence by splitting on period. Also produces the length as a feature."""
  name = 'test_splitter_len'
  enrichment_type = EnrichmentType.TEXT

  @override
  def fields(self) -> Field:
    return Field(repeated_field=Field(fields={
        'len': Field(dtype=DataType.INT32),
        'split': Field(dtype=DataType.STRING_SPAN)
    }))

  @override
  def compute(self, data: Iterable[RichData]) -> Iterable[ItemValue]:
    for text in data:
      if not isinstance(text, str):
        raise ValueError(f'Expected text to be a string, got {type(text)} instead.')
      sentences = [f'{sentence.strip()}.' for sentence in text.split('.') if sentence]
      yield [{
          'len': len(sentence),
          'split': TextSpan(start=text.index(sentence), end=text.index(sentence) + len(sentence))
      } for sentence in sentences]


class TestEntitySignal(Signal):
  """Split documents into sentence by splitting on period, generating entities.

  Also produces the length as a feature.
  """
  name = 'test_entity_len'
  enrichment_type = EnrichmentType.TEXT

  @override
  def fields(self) -> Field:
    return Field(repeated_field=EntityField(Field(
        dtype=DataType.STRING_SPAN), {'len': Field(dtype=DataType.INT32)}))

  @override
  def compute(self, data: Iterable[RichData]) -> Iterable[ItemValue]:
    for text in data:
      if not isinstance(text, str):
        raise ValueError(f'Expected text to be a string, got {type(text)} instead.')
      sentences = [f'{sentence.strip()}.' for sentence in text.split('.') if sentence]
      yield [
          Entity(entity=TextSpan(start=text.index(sentence),
                                 end=text.index(sentence) + len(sentence)),
                 metadata={'len': len(sentence)}) for sentence in sentences
      ]


class TestEmbeddingSumSignal(Signal):
  """Sums the embeddings to return a single floating point value."""
  name = 'test_embedding_sum'
  enrichment_type = EnrichmentType.TEXT
  vector_based = True

  @override
  def fields(self) -> Field:
    return Field(dtype=DataType.FLOAT32)

  @override
  def vector_compute(self, keys: Iterable[str], vector_store: VectorStore) -> Iterable[ItemValue]:
    if not self.embedding:
      raise ValueError('self.embedding is None.')

    # The signal just sums the values of the embedding.
    embedding_sums = vector_store.get(keys).sum(axis=1)
    for embedding_sum in embedding_sums.tolist():
      yield embedding_sum


class TestInvalidSignal(Signal):
  name = 'test_invalid_signal'
  enrichment_type = EnrichmentType.TEXT

  @override
  def fields(self) -> Field:
    return Field(dtype=DataType.INT32)

  @override
  def compute(self, data: Iterable[RichData]) -> Iterable[Optional[Item]]:
    # Return an invalid output that doesn't match the input length.
    return []


@pytest.mark.parametrize('db_cls', ALL_DBS)
class ComputeSignalItemsSuite:

  def test_signal_output_validation(self, tmp_path: pathlib.Path, db_cls: Type[DatasetDB]) -> None:
    signal = TestInvalidSignal()

    db = make_db(db_cls=db_cls,
                 tmp_path=tmp_path,
                 items=[{
                     UUID_COLUMN: '1',
                     'text': 'hello',
                 }, {
                     UUID_COLUMN: '2',
                     'text': 'hello world',
                 }],
                 schema=Schema(fields={
                     UUID_COLUMN: Field(dtype=DataType.STRING),
                     'text': Field(dtype=DataType.STRING),
                 }))

    with pytest.raises(
        ValueError,
        match='The enriched outputs \\(0\\) and the input data \\(2\\) do not have the same length'
    ):
      db.compute_signal_column(signal=signal, column=('text',))


@pytest.mark.parametrize('db_cls', ALL_DBS)
class StatsSuite:

  def test_simple_stats(self, tmp_path: pathlib.Path, db_cls: Type[DatasetDB]) -> None:
    db = make_db(db_cls, tmp_path, SIMPLE_ITEMS, SIMPLE_SCHEMA)

    result = db.stats(leaf_path='str')
    assert result == StatsResult(total_count=3, approx_count_distinct=2, avg_text_length=1)

    result = db.stats(leaf_path='float')
    assert result == StatsResult(total_count=3, approx_count_distinct=3, min_val=1.0, max_val=3.0)

    result = db.stats(leaf_path='bool')
    assert result == StatsResult(total_count=3, approx_count_distinct=2)

    result = db.stats(leaf_path='int')
    assert result == StatsResult(total_count=3, approx_count_distinct=2, min_val=1, max_val=2)

  def test_nested_stats(self, tmp_path: pathlib.Path, db_cls: Type[DatasetDB]) -> None:
    nested_items: list[Item] = [
        {
            'name': 'Name1',
            'addresses': [{
                'zips': [5, 8]
            }]
        },
        {
            'name': 'Name2',
            'addresses': [{
                'zips': [3]
            }, {
                'zips': [11, 8]
            }]
        },
        {
            'name': 'Name2',
            'addresses': []
        },  # No addresses.
        {
            'name': 'Name2',
            'addresses': [{
                'zips': []
            }]
        }  # No zips in the first address.
    ]
    nested_schema = Schema(
        fields={
            UUID_COLUMN: Field(dtype=DataType.STRING),
            'name': Field(dtype=DataType.STRING),
            'addresses': Field(repeated_field=Field(
                fields={'zips': Field(repeated_field=Field(dtype=DataType.INT32))}))
        })
    db = make_db(db_cls=db_cls, tmp_path=tmp_path, items=nested_items, schema=nested_schema)

    result = db.stats(leaf_path='name')
    assert result == StatsResult(total_count=4, approx_count_distinct=2, avg_text_length=5)

    result = db.stats(leaf_path='addresses.*.zips.*')
    assert result == StatsResult(total_count=5, approx_count_distinct=4, min_val=3, max_val=11)

  def test_stats_approximation(self, tmp_path: pathlib.Path, db_cls: Type[DatasetDB],
                               mocker: MockerFixture) -> None:
    sample_size = 5
    mocker.patch(f'{db_dataset_duckdb.__name__}.SAMPLE_SIZE_DISTINCT_COUNT', sample_size)

    nested_items: list[Item] = [{'feature': str(i)} for i in range(sample_size * 10)]
    nested_schema = Schema(fields={
        UUID_COLUMN: Field(dtype=DataType.STRING),
        'feature': Field(dtype=DataType.STRING)
    })
    db = make_db(db_cls=db_cls, tmp_path=tmp_path, items=nested_items, schema=nested_schema)

    result = db.stats(leaf_path='feature')
    assert result == StatsResult(total_count=50, approx_count_distinct=50, avg_text_length=1)

  def test_error_handling(self, tmp_path: pathlib.Path, db_cls: Type[DatasetDB]) -> None:
    db = make_db(db_cls=db_cls, tmp_path=tmp_path, items=SIMPLE_ITEMS, schema=SIMPLE_SCHEMA)

    with pytest.raises(ValueError, match='leaf_path must be provided'):
      db.stats(cast(Any, None))

    with pytest.raises(ValueError, match='Leaf "\\(\'unknown\',\\)" not found in dataset'):
      db.stats(leaf_path='unknown')


@pytest.mark.parametrize('db_cls', ALL_DBS)
class SelectGroupsSuite:

  def test_flat_data(self, tmp_path: pathlib.Path, db_cls: Type[DatasetDB]) -> None:
    items: list[Item] = [
        {
            'name': 'Name1',
            'age': 34,
            'active': False
        },
        {
            'name': 'Name2',
            'age': 45,
            'active': True
        },
        {
            'age': 17,
            'active': True
        },  # Missing "name".
        {
            'name': 'Name3',
            'active': True
        },  # Missing "age".
        {
            'name': 'Name4',
            'age': 55
        }  # Missing "active".
    ]
    schema = Schema(
        fields={
            UUID_COLUMN: Field(dtype=DataType.STRING),
            'name': Field(dtype=DataType.STRING),
            'age': Field(dtype=DataType.INT32),
            'active': Field(dtype=DataType.BOOLEAN)
        })
    db = make_db(db_cls=db_cls, tmp_path=tmp_path, items=items, schema=schema)

    result = db.select_groups(leaf_path='name').df()
    expected = pd.DataFrame.from_records([{
        'value': 'Name1',
        'count': 1
    }, {
        'value': 'Name2',
        'count': 1
    }, {
        'value': None,
        'count': 1
    }, {
        'value': 'Name3',
        'count': 1
    }, {
        'value': 'Name4',
        'count': 1
    }])
    pd.testing.assert_frame_equal(result, expected)

    result = db.select_groups(leaf_path='age', bins=[20, 50, 60]).df()
    expected = pd.DataFrame.from_records([
        {
            'value': 1,  # age 20-50.
            'count': 2
        },
        {
            'value': 0,  # age < 20.
            'count': 1
        },
        {
            'value': None,  # Missing age.
            'count': 1
        },
        {
            'value': 2,  # age 50-60.
            'count': 1
        }
    ])
    pd.testing.assert_frame_equal(result, expected)

    result = db.select_groups(leaf_path='active').df()
    expected = pd.DataFrame.from_records([
        {
            'value': True,
            'count': 3
        },
        {
            'value': False,
            'count': 1
        },
        {
            'value': None,  # Missing "active".
            'count': 1
        }
    ])
    pd.testing.assert_frame_equal(result, expected)

  def test_result_is_iterable(self, tmp_path: pathlib.Path, db_cls: Type[DatasetDB]) -> None:
    items: list[Item] = [
        {
            'active': False
        },
        {
            'active': True
        },
        {
            'active': True
        },
        {
            'active': True
        },
        {}  # Missing "active".
    ]
    schema = Schema(fields={
        UUID_COLUMN: Field(dtype=DataType.STRING),
        'active': Field(dtype=DataType.BOOLEAN)
    })
    db = make_db(db_cls=db_cls, tmp_path=tmp_path, items=items, schema=schema)

    result = db.select_groups(leaf_path='active')
    groups = list(result)
    assert groups == [(True, 3), (False, 1), (None, 1)]

  def test_list_of_structs(self, tmp_path: pathlib.Path, db_cls: Type[DatasetDB]) -> None:
    items: list[Item] = [{
        'list_of_structs': [{
            'name': 'a'
        }, {
            'name': 'b'
        }]
    }, {
        'list_of_structs': [{
            'name': 'c'
        }, {
            'name': 'a'
        }, {
            'name': 'd'
        }]
    }, {
        'list_of_structs': [{
            'name': 'd'
        }]
    }]
    schema = Schema(
        fields={
            UUID_COLUMN: Field(dtype=DataType.STRING),
            'list_of_structs': Field(repeated_field=Field(
                fields={'name': Field(dtype=DataType.STRING)})),
        })
    db = make_db(db_cls=db_cls, tmp_path=tmp_path, items=items, schema=schema)

    result = db.select_groups(leaf_path='list_of_structs.*.name').df()
    expected = pd.DataFrame.from_records([{
        'value': 'a',
        'count': 2
    }, {
        'value': 'd',
        'count': 2
    }, {
        'value': 'b',
        'count': 1
    }, {
        'value': 'c',
        'count': 1
    }])
    pd.testing.assert_frame_equal(result, expected)

  def test_nested_lists(self, tmp_path: pathlib.Path, db_cls: Type[DatasetDB]) -> None:
    items: list[Item] = [{
        'nested_list': [[{
            'name': 'a'
        }], [{
            'name': 'b'
        }]]
    }, {
        'nested_list': [[{
            'name': 'c'
        }, {
            'name': 'a'
        }], [{
            'name': 'd'
        }]]
    }, {
        'nested_list': [[{
            'name': 'd'
        }]]
    }]
    schema = Schema(
        fields={
            UUID_COLUMN: Field(dtype=DataType.STRING),
            'nested_list': Field(repeated_field=Field(repeated_field=Field(
                fields={'name': Field(dtype=DataType.STRING)}))),
        })
    db = make_db(db_cls=db_cls, tmp_path=tmp_path, items=items, schema=schema)

    result = db.select_groups(leaf_path='nested_list.*.*.name').df()
    expected = pd.DataFrame.from_records([{
        'value': 'a',
        'count': 2
    }, {
        'value': 'd',
        'count': 2
    }, {
        'value': 'b',
        'count': 1
    }, {
        'value': 'c',
        'count': 1
    }])
    pd.testing.assert_frame_equal(result, expected)

  def test_nested_struct(self, tmp_path: pathlib.Path, db_cls: Type[DatasetDB]) -> None:
    items: list[Item] = [
        {
            'nested_struct': {
                'struct': {
                    'name': 'c'
                }
            }
        },
        {
            'nested_struct': {
                'struct': {
                    'name': 'b'
                }
            }
        },
        {
            'nested_struct': {
                'struct': {
                    'name': 'a'
                }
            }
        },
    ]
    schema = Schema(
        fields={
            UUID_COLUMN: Field(dtype=DataType.STRING),
            'nested_struct': Field(
                fields={'struct': Field(fields={'name': Field(dtype=DataType.STRING)})}),
        })
    db = make_db(db_cls=db_cls, tmp_path=tmp_path, items=items, schema=schema)

    result = db.select_groups(leaf_path='nested_struct.struct.name').df()
    expected = pd.DataFrame.from_records([{
        'value': 'c',
        'count': 1
    }, {
        'value': 'b',
        'count': 1
    }, {
        'value': 'a',
        'count': 1
    }])
    pd.testing.assert_frame_equal(result, expected)

  def test_named_bins(self, tmp_path: pathlib.Path, db_cls: Type[DatasetDB]) -> None:
    items: list[Item] = [{
        'age': 34,
    }, {
        'age': 45,
    }, {
        'age': 17,
    }, {
        'age': 80
    }, {
        'age': 55
    }]
    schema = Schema(fields={
        UUID_COLUMN: Field(dtype=DataType.STRING),
        'age': Field(dtype=DataType.INT32),
    })
    db = make_db(db_cls=db_cls, tmp_path=tmp_path, items=items, schema=schema)

    result = db.select_groups(leaf_path='age',
                              bins=NamedBins(bins=[20, 50, 65],
                                             labels=['young', 'adult', 'middle-aged',
                                                     'senior'])).df()
    expected = pd.DataFrame.from_records([
        {
            'value': 'adult',  # age 20-50.
            'count': 2
        },
        {
            'value': 'young',  # age < 20.
            'count': 1
        },
        {
            'value': 'senior',  # age > 65.
            'count': 1
        },
        {
            'value': 'middle-aged',  # age 50-65.
            'count': 1
        }
    ])
    pd.testing.assert_frame_equal(result, expected)

  def test_invalid_leaf(self, tmp_path: pathlib.Path, db_cls: Type[DatasetDB]) -> None:
    items: list[Item] = [
        {
            'nested_struct': {
                'struct': {
                    'name': 'c'
                }
            }
        },
        {
            'nested_struct': {
                'struct': {
                    'name': 'b'
                }
            }
        },
        {
            'nested_struct': {
                'struct': {
                    'name': 'a'
                }
            }
        },
    ]
    schema = Schema(
        fields={
            UUID_COLUMN: Field(dtype=DataType.STRING),
            'nested_struct': Field(
                fields={'struct': Field(fields={'name': Field(dtype=DataType.STRING)})}),
        })
    db = make_db(db_cls=db_cls, tmp_path=tmp_path, items=items, schema=schema)

    with pytest.raises(ValueError,
                       match=re.escape("Leaf \"('nested_struct',)\" not found in dataset")):
      db.select_groups(leaf_path='nested_struct')

    with pytest.raises(
        ValueError, match=re.escape("Leaf \"('nested_struct', 'struct')\" not found in dataset")):
      db.select_groups(leaf_path='nested_struct.struct')

    with pytest.raises(
        ValueError,
        match=re.escape("Leaf \"('nested_struct', 'struct', 'wrong_name')\" not found in dataset")):
      db.select_groups(leaf_path='nested_struct.struct.wrong_name')

  def test_too_many_distinct(self, tmp_path: pathlib.Path, db_cls: Type[DatasetDB],
                             mocker: MockerFixture) -> None:
    too_many_distinct = 5
    mocker.patch(f'{db_dataset.__name__}.TOO_MANY_DISTINCT', too_many_distinct)

    items: list[Item] = [{'feature': str(i)} for i in range(too_many_distinct + 10)]
    schema = Schema(fields={
        UUID_COLUMN: Field(dtype=DataType.STRING),
        'feature': Field(dtype=DataType.STRING)
    })
    db = make_db(db_cls=db_cls, tmp_path=tmp_path, items=items, schema=schema)

    with pytest.raises(ValueError,
                       match=re.escape('Leaf "(\'feature\',)" has too many unique values: 15')):
      db.select_groups('feature')

  def test_bins_are_required_for_float(self, tmp_path: pathlib.Path,
                                       db_cls: Type[DatasetDB]) -> None:
    items: list[Item] = [{'feature': float(i)} for i in range(5)]
    schema = Schema(fields={
        UUID_COLUMN: Field(dtype=DataType.STRING),
        'feature': Field(dtype=DataType.FLOAT32)
    })
    db = make_db(db_cls=db_cls, tmp_path=tmp_path, items=items, schema=schema)

    with pytest.raises(
        ValueError,
        match=re.escape('"bins" needs to be defined for the int/float leaf "(\'feature\',)"')):
      db.select_groups('feature')
