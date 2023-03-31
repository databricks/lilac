"""Implementation-agnostic tests of the Dataset DB API."""

import os
import pathlib
from typing import Any, Generator, Iterable, Optional, Type, cast

import numpy as np
import pytest
from pytest_mock import MockerFixture
from typing_extensions import override

from ..embeddings.embedding_index import GetEmbeddingIndexFn
from ..embeddings.embedding_registry import clear_embedding_registry, register_embed_fn
from ..schema import (
    TEXT_SPAN_END_FEATURE,
    TEXT_SPAN_START_FEATURE,
    UUID_COLUMN,
    DataType,
    EnrichmentType,
    Field,
    Item,
    ItemValue,
    Path,
    RichData,
    Schema,
    TextSpan,
)
from ..signals.signal import Signal
from ..signals.signal_registry import clear_signal_registry, register_signal
from . import db_dataset_duckdb
from .db_dataset import Column, DatasetDB, DatasetManifest, SortOrder, StatsResult
from .db_dataset_duckdb import DatasetDuckDB
from .db_dataset_test_utils import TEST_DATASET_NAME, TEST_NAMESPACE, make_db

ALL_DBS = [DatasetDuckDB]

SIMPLE_DATASET_NAME = 'simple'

SIMPLE_ITEMS: list[Item] = [{
    UUID_COLUMN: b'1' * 16,
    'str': 'a',
    'int': 1,
    'bool': False,
    'float': 3.0
}, {
    UUID_COLUMN: b'2' * 16,
    'str': 'b',
    'int': 2,
    'bool': True,
    'float': 2.0
}, {
    UUID_COLUMN: b'2' * 16,
    'str': 'b',
    'int': 2,
    'bool': True,
    'float': 1.0
}]

SIMPLE_SCHEMA = Schema(
    fields={
        UUID_COLUMN: Field(dtype=DataType.BINARY),
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


def embed(examples: Iterable[RichData]) -> np.ndarray:
  """Embed the examples, use a hashmap to the vector for simplicity."""
  return np.array([STR_EMBEDDINGS[cast(str, example)] for example in examples])


@pytest.fixture(scope='module', autouse=True)
def setup_teardown() -> Iterable[None]:
  # Setup.
  register_signal(TestSignal)
  register_signal(TestSplitterWithLen)
  register_signal(TestEmbeddingSumSignal)
  # We register the embed function like this so we can mock it and assert how many times its called.
  register_embed_fn(TEST_EMBEDDING_NAME)(embed)

  # Unit test runs.
  yield

  # Teardown.
  clear_signal_registry()
  clear_embedding_registry()


@pytest.fixture(autouse=True)
def set_data_path(tmp_path: pathlib.Path) -> Generator:
  data_path = os.environ.get('LILAC_DATA_PATH', None)
  os.environ['LILAC_DATA_PATH'] = str(tmp_path)

  yield

  os.environ['LILAC_DATA_PATH'] = data_path or ''


@pytest.mark.parametrize('db_cls', ALL_DBS)
class SelectRowsSuite:

  def test_default(self, tmp_path: pathlib.Path, db_cls: Type[DatasetDB]) -> None:
    db = make_db(db_cls, tmp_path, SIMPLE_ITEMS, SIMPLE_SCHEMA)

    result = db.select_rows()

    assert list(result) == SIMPLE_ITEMS

  def test_columns(self, tmp_path: pathlib.Path, db_cls: Type[DatasetDB]) -> None:
    db = make_db(db_cls, tmp_path, SIMPLE_ITEMS, SIMPLE_SCHEMA)

    result = db.select_rows(columns=['str', 'float'])

    assert list(result) == [{
        UUID_COLUMN: b'1' * 16,
        'str': 'a',
        'float': 3.0
    }, {
        UUID_COLUMN: b'2' * 16,
        'str': 'b',
        'float': 2.0
    }, {
        UUID_COLUMN: b'2' * 16,
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
                                                    UUID_COLUMN: Field(dtype=DataType.BINARY),
                                                    'str': Field(dtype=DataType.STRING),
                                                    'int': Field(dtype=DataType.INT64),
                                                    'bool': Field(dtype=DataType.BOOLEAN),
                                                    'float': Field(dtype=DataType.FLOAT64),
                                                }),
                                            num_items=3)

    test_signal = TestSignal()
    db.compute_signal_columns(signal=test_signal, column='str')

    result = db.select_rows(columns=['str', 'test_signal(str)'])

    assert list(result) == [{
        UUID_COLUMN: b'1' * 16,
        'str': 'a',
        'test_signal(str)': {
            'len': 1,
            'flen': 1.0
        }
    }, {
        UUID_COLUMN: b'2' * 16,
        'str': 'b',
        'test_signal(str)': {
            'len': 1,
            'flen': 1.0
        }
    }, {
        UUID_COLUMN: b'2' * 16,
        'str': 'b',
        'test_signal(str)': {
            'len': 1,
            'flen': 1.0
        }
    }]

    # Check the enriched dataset manifest has 'text' enriched.
    assert db.manifest() == DatasetManifest(namespace=TEST_NAMESPACE,
                                            dataset_name=TEST_DATASET_NAME,
                                            data_schema=Schema(
                                                fields={
                                                    UUID_COLUMN:
                                                        Field(dtype=DataType.BINARY),
                                                    'str':
                                                        Field(dtype=DataType.STRING),
                                                    'int':
                                                        Field(dtype=DataType.INT64),
                                                    'bool':
                                                        Field(dtype=DataType.BOOLEAN),
                                                    'float':
                                                        Field(dtype=DataType.FLOAT64),
                                                    'test_signal(str)':
                                                        Field(fields={
                                                            'len': Field(dtype=DataType.INT32),
                                                            'flen': Field(dtype=DataType.FLOAT32)
                                                        },
                                                              enriched=True)
                                                }),
                                            num_items=3)

    # Select a specific signal leaf test_signal.flen.
    result = db.select_rows(columns=['str', ('test_signal(str)', 'flen')])

    assert list(result) == [{
        UUID_COLUMN: b'1' * 16,
        'str': 'a',
        'test_signal(str).flen': 1.0
    }, {
        UUID_COLUMN: b'2' * 16,
        'str': 'b',
        'test_signal(str).flen': 1.0
    }, {
        UUID_COLUMN: b'2' * 16,
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
        UUID_COLUMN: b'1' * 16,
        'str': 'a',
        'flen': 1.0,
        'len': 1
    }, {
        UUID_COLUMN: b'2' * 16,
        'str': 'b',
        'flen': 1.0,
        'len': 1
    }, {
        UUID_COLUMN: b'2' * 16,
        'str': 'b',
        'flen': 1.0,
        'len': 1
    }]

  def test_signal_on_repeated_field(self, tmp_path: pathlib.Path, db_cls: Type[DatasetDB]) -> None:
    db = make_db(db_cls,
                 tmp_path,
                 items=[{
                     UUID_COLUMN: b'1' * 16,
                     'text': ['hello', 'everybody'],
                 }, {
                     UUID_COLUMN: b'2' * 16,
                     'text': ['hello2', 'everybody2'],
                 }],
                 schema=Schema(
                     fields={
                         UUID_COLUMN: Field(dtype=DataType.BINARY),
                         'text': Field(repeated_field=Field(dtype=DataType.STRING)),
                     }))
    test_signal = TestSignal()
    # Run the signal on the repeated field.
    db.compute_signal_columns(signal=test_signal, column=('text', '*'))

    # Check the enriched dataset manifest has 'text' enriched.
    assert db.manifest() == DatasetManifest(
        namespace=TEST_NAMESPACE,
        dataset_name=TEST_DATASET_NAME,
        data_schema=Schema(
            fields={
                UUID_COLUMN:
                    Field(dtype=DataType.BINARY),
                'text':
                    Field(repeated_field=Field(dtype=DataType.STRING)),
                'test_signal(text)':
                    Field(repeated_field=Field(fields={
                        'len': Field(dtype=DataType.INT32),
                        'flen': Field(dtype=DataType.FLOAT32)
                    },
                                               enriched=True),
                          enriched=True)
            }),
        num_items=2)

    result = db.select_rows(columns=[('test_signal(text)')])

    assert list(result) == [{
        UUID_COLUMN: b'1' * 16,
        'test_signal(text)': [{
            'len': 5,
            'flen': 5.0
        }, {
            'len': 9,
            'flen': 9.0
        }]
    }, {
        UUID_COLUMN: b'2' * 16,
        'test_signal(text)': [{
            'len': 6,
            'flen': 6.0
        }, {
            'len': 10,
            'flen': 10.0
        }]
    }]

  def test_source_joined_with_named_signal_column(self, tmp_path: pathlib.Path,
                                                  db_cls: Type[DatasetDB]) -> None:
    db = make_db(db_cls, tmp_path, SIMPLE_ITEMS, SIMPLE_SCHEMA)
    assert db.manifest() == DatasetManifest(namespace=TEST_NAMESPACE,
                                            dataset_name=TEST_DATASET_NAME,
                                            data_schema=Schema(
                                                fields={
                                                    UUID_COLUMN: Field(dtype=DataType.BINARY),
                                                    'str': Field(dtype=DataType.STRING),
                                                    'int': Field(dtype=DataType.INT64),
                                                    'bool': Field(dtype=DataType.BOOLEAN),
                                                    'float': Field(dtype=DataType.FLOAT64),
                                                }),
                                            num_items=3)

    test_signal = TestSignal()
    db.compute_signal_columns(signal=test_signal,
                              column='str',
                              signal_column_name='test_signal_on_str')

    result = db.select_rows(columns=['str', 'test_signal_on_str'])

    assert list(result) == [{
        UUID_COLUMN: b'1' * 16,
        'str': 'a',
        'test_signal_on_str': {
            'len': 1,
            'flen': 1.0
        }
    }, {
        UUID_COLUMN: b'2' * 16,
        'str': 'b',
        'test_signal_on_str': {
            'len': 1,
            'flen': 1.0
        }
    }, {
        UUID_COLUMN: b'2' * 16,
        'str': 'b',
        'test_signal_on_str': {
            'len': 1,
            'flen': 1.0
        }
    }]

    # Check the enriched dataset manifest has 'text' enriched.
    assert db.manifest() == DatasetManifest(namespace=TEST_NAMESPACE,
                                            dataset_name=TEST_DATASET_NAME,
                                            data_schema=Schema(
                                                fields={
                                                    UUID_COLUMN:
                                                        Field(dtype=DataType.BINARY),
                                                    'str':
                                                        Field(dtype=DataType.STRING),
                                                    'int':
                                                        Field(dtype=DataType.INT64),
                                                    'bool':
                                                        Field(dtype=DataType.BOOLEAN),
                                                    'float':
                                                        Field(dtype=DataType.FLOAT64),
                                                    'test_signal_on_str':
                                                        Field(fields={
                                                            'len': Field(dtype=DataType.INT32),
                                                            'flen': Field(dtype=DataType.FLOAT32)
                                                        },
                                                              enriched=True)
                                                }),
                                            num_items=3)

  def test_text_splitter(self, tmp_path: pathlib.Path, db_cls: Type[DatasetDB]) -> None:
    db = make_db(db_cls=db_cls,
                 tmp_path=tmp_path,
                 items=[{
                     UUID_COLUMN: b'1' * 16,
                     'text': '[1, 1] first sentence. [1, 1] second sentence.',
                 }, {
                     UUID_COLUMN: b'2' * 16,
                     'text': 'b2 [2, 1] first sentence. [2, 1] second sentence.',
                 }],
                 schema=Schema(fields={
                     UUID_COLUMN: Field(dtype=DataType.BINARY),
                     'text': Field(dtype=DataType.STRING),
                 }))

    db.compute_signal_columns(signal=TestSplitterWithLen(), column='text')

    result = db.select_rows(columns=['text', 'test_splitter_len(text)'])
    expected_result = [{
        UUID_COLUMN:
            b'1' * 16,
        'text':
            '[1, 1] first sentence. [1, 1] second sentence.',
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
        UUID_COLUMN:
            b'2' * 16,
        'text':
            'b2 [2, 1] first sentence. [2, 1] second sentence.',
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

  def test_embedding_signal(self, tmp_path: pathlib.Path, db_cls: Type[DatasetDB]) -> None:
    db = make_db(db_cls=db_cls,
                 tmp_path=tmp_path,
                 items=[{
                     UUID_COLUMN: b'1' * 16,
                     'text': 'hello.',
                 }, {
                     UUID_COLUMN: b'2' * 16,
                     'text': 'hello2.',
                 }],
                 schema=Schema(fields={
                     UUID_COLUMN: Field(dtype=DataType.BINARY),
                     'text': Field(dtype=DataType.STRING),
                 }))

    db.compute_embedding_index(embedding=TEST_EMBEDDING_NAME, column='text')

    db.compute_signal_columns(signal=TestEmbeddingSumSignal(embedding=TEST_EMBEDDING_NAME),
                              column='text',
                              signal_column_name='text_emb_sum')

    assert db.manifest() == DatasetManifest(
        namespace=TEST_NAMESPACE,
        dataset_name=TEST_DATASET_NAME,
        data_schema=Schema(
            fields={
                UUID_COLUMN: Field(dtype=DataType.BINARY),
                'text': Field(dtype=DataType.STRING),
                'text_emb_sum': Field(dtype=DataType.FLOAT32, enriched=True)
            }),
        num_items=2)

    result = db.select_rows(columns=['text', 'text_emb_sum'])
    expected_result = [{
        UUID_COLUMN: b'1' * 16,
        'text': 'hello.',
        'text_emb_sum': 1.0
    }, {
        UUID_COLUMN: b'2' * 16,
        'text': 'hello2.',
        'text_emb_sum': 2.0
    }]
    assert list(result) == expected_result

  def test_embedding_signal_splits(self, tmp_path: pathlib.Path, db_cls: Type[DatasetDB]) -> None:
    db = make_db(db_cls=db_cls,
                 tmp_path=tmp_path,
                 items=[{
                     UUID_COLUMN: b'1' * 16,
                     'text': 'hello. hello2.',
                 }, {
                     UUID_COLUMN: b'2' * 16,
                     'text': 'hello world. hello world2.',
                 }],
                 schema=Schema(fields={
                     UUID_COLUMN: Field(dtype=DataType.BINARY),
                     'text': Field(dtype=DataType.STRING),
                 }))

    db.compute_signal_columns(signal=TestSplitterWithLen(),
                              column='text',
                              signal_column_name='text_sentences')

    db.compute_embedding_index(embedding=TEST_EMBEDDING_NAME,
                               column=('text_sentences', '*', 'split'))

    db.compute_signal_columns(signal=TestEmbeddingSumSignal(embedding=TEST_EMBEDDING_NAME),
                              column=('text_sentences', '*', 'split'),
                              signal_column_name='text_sentences_emb_sum')

    assert db.manifest() == DatasetManifest(
        namespace=TEST_NAMESPACE,
        dataset_name=TEST_DATASET_NAME,
        data_schema=Schema(
            fields={
                UUID_COLUMN:
                    Field(dtype=DataType.BINARY),
                'text':
                    Field(dtype=DataType.STRING),
                'text_sentences_emb_sum':
                    Field(repeated_field=Field(
                        fields={'split': Field(dtype=DataType.FLOAT32, enriched=True)})),
                'text_sentences':
                    Field(repeated_field=Field(
                        fields={
                            'len': Field(dtype=DataType.INT32),
                            'split': Field(dtype=DataType.STRING_SPAN, refers_to=('text',))
                        }),
                          enriched=True)
            }),
        num_items=2)

    result = db.select_rows(columns=['text', 'text_sentences', 'text_sentences_emb_sum'])
    expected_result = [{
        UUID_COLUMN: b'1' * 16,
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
        UUID_COLUMN: b'2' * 16,
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
                     UUID_COLUMN: b'1' * 16,
                     'text': 'hello',
                     'text2': ['hello', 'world'],
                 }, {
                     UUID_COLUMN: b'2' * 16,
                     'text': 'hello world',
                     'text2': ['hello2', 'world2'],
                 }],
                 schema=Schema(
                     fields={
                         UUID_COLUMN: Field(dtype=DataType.BINARY),
                         'text': Field(dtype=DataType.STRING),
                         'text2': Field(repeated_field=Field(dtype=DataType.STRING)),
                     }))
    test_signal = TestSignal()
    db.compute_signal_columns(signal=test_signal, column='text')
    db.compute_signal_columns(signal=test_signal, column=('text2', '*'))

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
        UUID_COLUMN: b'2' * 16,
        'float': 1.0
    }, {
        UUID_COLUMN: b'2' * 16,
        'float': 2.0
    }, {
        UUID_COLUMN: b'1' * 16,
        'float': 3.0
    }]

    result = db.select_rows(columns=[UUID_COLUMN, 'float'],
                            sort_by=['float'],
                            sort_order=SortOrder.DESC)

    assert list(result) == [{
        UUID_COLUMN: b'1' * 16,
        'float': 3.0
    }, {
        UUID_COLUMN: b'2' * 16,
        'float': 2.0
    }, {
        UUID_COLUMN: b'2' * 16,
        'float': 1.0
    }]

  def test_limit(self, tmp_path: pathlib.Path, db_cls: Type[DatasetDB]) -> None:
    db = make_db(db_cls, tmp_path, SIMPLE_ITEMS, SIMPLE_SCHEMA)

    result = db.select_rows(columns=[UUID_COLUMN, 'float'],
                            sort_by=['float'],
                            sort_order=SortOrder.ASC,
                            limit=2)
    assert list(result) == [{
        UUID_COLUMN: b'2' * 16,
        'float': 1.0
    }, {
        UUID_COLUMN: b'2' * 16,
        'float': 2.0
    }]


class TestSignal(Signal):
  name = 'test_signal'
  enrichment_type = EnrichmentType.TEXT
  embedding_based = False

  @override
  def fields(self, input_column: Path) -> Field:
    return Field(fields={'len': Field(dtype=DataType.INT32), 'flen': Field(dtype=DataType.FLOAT32)})

  @override
  def compute(
      self,
      data: Optional[Iterable[RichData]] = None,
      keys: Optional[Iterable[bytes]] = None,
      get_embedding_index: Optional[GetEmbeddingIndexFn] = None) -> Iterable[Optional[Item]]:
    if data is None:
      raise ValueError('data is not defined')
    return [{'len': len(text_content), 'flen': float(len(text_content))} for text_content in data]


class TestSplitterWithLen(Signal):
  """Split documents into sentence by splitting on period. Also produces the length as a feature."""
  name = 'test_splitter_len'
  enrichment_type = EnrichmentType.TEXT

  @override
  def fields(self, input_column: Path) -> Field:
    return Field(repeated_field=Field(
        fields={
            'len': Field(dtype=DataType.INT32),
            'split': Field(dtype=DataType.STRING_SPAN, refers_to=input_column)
        }))

  @override
  def compute(self,
              data: Optional[Iterable[RichData]] = None,
              keys: Optional[Iterable[bytes]] = None,
              get_embedding_index: Optional[GetEmbeddingIndexFn] = None) -> Iterable[ItemValue]:
    if data is None:
      raise ValueError('Sentence splitter requires text data.')

    for text in data:
      if not isinstance(text, str):
        raise ValueError(f'Expected text to be a string, got {type(text)} instead.')
      sentences = [f'{sentence.strip()}.' for sentence in text.split('.') if sentence]
      yield [{
          'len': len(sentence),
          'split': TextSpan(start=text.index(sentence), end=text.index(sentence) + len(sentence))
      } for sentence in sentences]


class TestEmbeddingSumSignal(Signal):
  """Sums the embeddings to return a single floating point value."""
  name = 'test_embedding_sum'
  enrichment_type = EnrichmentType.TEXT
  embedding_based = True

  @override
  def fields(self, input_column: Path) -> Field:
    return Field(dtype=DataType.FLOAT32)

  @override
  def compute(self,
              data: Optional[Iterable[RichData]] = None,
              keys: Optional[Iterable[bytes]] = None,
              get_embedding_index: Optional[GetEmbeddingIndexFn] = None) -> Iterable[ItemValue]:
    if keys is None:
      raise ValueError('Embedding sum signal requires keys.')
    if get_embedding_index is None:
      raise ValueError('get_embedding_index is None.')
    if not self.embedding:
      raise ValueError('self.embedding is None.')

    embedding_index = get_embedding_index(self.embedding, keys)
    # The signal just sums the values of the embedding.
    embedding_sums = embedding_index.embeddings.sum(axis=1)
    for embedding_sum in embedding_sums.tolist():
      yield embedding_sum


class TestInvalidSignal(Signal):
  name = 'test_invalid_signal'
  enrichment_type = EnrichmentType.TEXT

  @override
  def fields(self, input_column: Path) -> Field:
    return Field(dtype=DataType.INT32)

  @override
  def compute(
      self,
      data: Optional[Iterable[RichData]] = None,
      keys: Optional[Iterable[bytes]] = None,
      get_embedding_index: Optional[GetEmbeddingIndexFn] = None) -> Iterable[Optional[Item]]:
    # Return an invalid output that doesn't match the input length.
    return []


@pytest.mark.parametrize('db_cls', ALL_DBS)
class ComputeSignalItemsSuite:

  def test_signal_output_validation(self, tmp_path: pathlib.Path, db_cls: Type[DatasetDB]) -> None:
    signal = TestInvalidSignal()

    db = make_db(db_cls=db_cls,
                 tmp_path=tmp_path,
                 items=[{
                     UUID_COLUMN: b'1' * 16,
                     'text': 'hello',
                 }, {
                     UUID_COLUMN: b'2' * 16,
                     'text': 'hello world',
                 }],
                 schema=Schema(fields={
                     UUID_COLUMN: Field(dtype=DataType.BINARY),
                     'text': Field(dtype=DataType.STRING),
                 }))

    with pytest.raises(
        ValueError,
        match='The enriched outputs \\(0\\) and the input data \\(2\\) do not have the same length'
    ):
      db.compute_signal_columns(signal=signal, column=('text',))


@pytest.mark.parametrize('db_cls', ALL_DBS)
class StatsSuite:

  def test_simple_stats(self, tmp_path: pathlib.Path, db_cls: Type[DatasetDB]) -> None:
    db = make_db(db_cls, tmp_path, SIMPLE_ITEMS, SIMPLE_SCHEMA)

    result = db.stats(leaf_path='str')
    assert result == StatsResult(approx_count_distinct=2, avg_text_length=1)

    result = db.stats(leaf_path='float')
    assert result == StatsResult(approx_count_distinct=3, min_val=1.0, max_val=3.0)

    result = db.stats(leaf_path='bool')
    assert result == StatsResult(approx_count_distinct=2)

    result = db.stats(leaf_path='int')
    assert result == StatsResult(approx_count_distinct=2, min_val=1, max_val=2)

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
            UUID_COLUMN:
                Field(dtype=DataType.BINARY),
            'name':
                Field(dtype=DataType.STRING),
            'addresses':
                Field(repeated_field=Field(
                    fields={'zips': Field(repeated_field=Field(dtype=DataType.INT32))}))
        })
    db = make_db(db_cls=db_cls, tmp_path=tmp_path, items=nested_items, schema=nested_schema)

    result = db.stats(leaf_path='name')
    assert result == StatsResult(approx_count_distinct=2, avg_text_length=5)

    result = db.stats(leaf_path='addresses.*.zips.*')
    assert result == StatsResult(approx_count_distinct=4, min_val=3, max_val=11)

  def test_stats_approximation(self, tmp_path: pathlib.Path, db_cls: Type[DatasetDB],
                               mocker: MockerFixture) -> None:
    sample_size = 5
    mocker.patch(f'{db_dataset_duckdb.__name__}.SAMPLE_SIZE_DISTINCT_COUNT', sample_size)

    nested_items: list[Item] = [{'feature': str(i)} for i in range(sample_size * 10)]
    nested_schema = Schema(fields={
        UUID_COLUMN: Field(dtype=DataType.BINARY),
        'feature': Field(dtype=DataType.STRING)
    })
    db = make_db(db_cls=db_cls, tmp_path=tmp_path, items=nested_items, schema=nested_schema)

    result = db.stats(leaf_path='feature')
    assert result == StatsResult(approx_count_distinct=50, avg_text_length=1)

  def test_error_handling(self, tmp_path: pathlib.Path, db_cls: Type[DatasetDB]) -> None:
    db = make_db(db_cls=db_cls, tmp_path=tmp_path, items=SIMPLE_ITEMS, schema=SIMPLE_SCHEMA)

    with pytest.raises(ValueError, match='leaf_path must be provided'):
      db.stats(cast(Any, None))

    with pytest.raises(ValueError, match='Leaf "\\(\'unknown\',\\)" not found in dataset'):
      db.stats(leaf_path='unknown')
