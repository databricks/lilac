"""Implementation-agnostic tests of the Dataset DB API."""

import pathlib
from typing import Iterable, Optional, Type

import pytest
from typing_extensions import override

from ..embeddings.embedding_index import GetEmbeddingIndexFn
from ..schema import UUID_COLUMN, DataType, EnrichmentType, Field, Item, RichData, Schema
from ..signals.signal import Signal
from ..signals.signal_registry import clear_signal_registry, register_signal
from ..signals.splitters.splitter import (
    TEXT_SPAN_END_FEATURE,
    TEXT_SPAN_FEATURE_NAME,
    TEXT_SPAN_START_FEATURE,
    SpanFields,
    SpanItem,
)
from .db_dataset import Column, DatasetDB, DatasetManifest, SortOrder
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


@pytest.fixture(scope='module', autouse=True)
def setup_teardown() -> Iterable[None]:
  # Setup.
  register_signal(TestSignal)
  register_signal(TestSplitterWithLen)

  # Unit test runs.
  yield

  # Teardown.
  clear_signal_registry()


class SelectRowsSuite:

  @pytest.mark.parametrize('db_cls', ALL_DBS)
  def test_default(self, tmp_path: pathlib.Path, db_cls: Type[DatasetDB]) -> None:
    db = make_db(db_cls, tmp_path, SIMPLE_ITEMS, SIMPLE_SCHEMA)

    result = db.select_rows()

    assert list(result) == SIMPLE_ITEMS

  @pytest.mark.parametrize('db_cls', ALL_DBS)
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

  @pytest.mark.parametrize('db_cls', ALL_DBS)
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
                                                }))

    test_signal = TestSignal()
    db.compute_signal_columns(signal=test_signal, column='str')

    result = db.select_rows(columns=['str', 'str(test_signal)'])

    assert list(result) == [{
        UUID_COLUMN: b'1' * 16,
        'str': 'a',
        'str(test_signal)': {
            'len': 1,
            'flen': 1.0
        }
    }, {
        UUID_COLUMN: b'2' * 16,
        'str': 'b',
        'str(test_signal)': {
            'len': 1,
            'flen': 1.0
        }
    }, {
        UUID_COLUMN: b'2' * 16,
        'str': 'b',
        'str(test_signal)': {
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
                                                    'str(test_signal)':
                                                        Field(fields={
                                                            'len': Field(dtype=DataType.INT32),
                                                            'flen': Field(dtype=DataType.FLOAT32)
                                                        },
                                                              enriched=True)
                                                }))

    # Select a specific signal leaf test_signal.flen.
    result = db.select_rows(columns=['str', ('str(test_signal)', 'flen')])

    assert list(result) == [{
        UUID_COLUMN: b'1' * 16,
        'str': 'a',
        'str(test_signal).flen': 1.0
    }, {
        UUID_COLUMN: b'2' * 16,
        'str': 'b',
        'str(test_signal).flen': 1.0
    }, {
        UUID_COLUMN: b'2' * 16,
        'str': 'b',
        'str(test_signal).flen': 1.0
    }]

    # Select multiple signal leafs with aliasing.
    result = db.select_rows(columns=[
        'str',
        Column(('str(test_signal)', 'flen'), alias='flen'),
        Column(('str(test_signal)', 'len'), alias='len')
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

  @pytest.mark.parametrize('db_cls', ALL_DBS)
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
                'text(test_signal)':
                    Field(repeated_field=Field(fields={
                        'len': Field(dtype=DataType.INT32),
                        'flen': Field(dtype=DataType.FLOAT32)
                    },
                                               enriched=True),
                          enriched=True)
            }))

    result = db.select_rows(columns=[('text(test_signal)')])

    assert list(result) == [{
        UUID_COLUMN: b'1' * 16,
        'text(test_signal)': [{
            'len': 5,
            'flen': 5.0
        }, {
            'len': 9,
            'flen': 9.0
        }]
    }, {
        UUID_COLUMN: b'2' * 16,
        'text(test_signal)': [{
            'len': 6,
            'flen': 6.0
        }, {
            'len': 10,
            'flen': 10.0
        }]
    }]

  @pytest.mark.parametrize('db_cls', ALL_DBS)
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
                                                }))

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
                                                }))

  @pytest.mark.parametrize('db_cls', ALL_DBS)
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

    result = db.select_rows(columns=['text', 'text(test_splitter)'])
    expected_result = [{
        UUID_COLUMN: b'1' * 16,
        'text': '[1, 1] first sentence. [1, 1] second sentence.',
        'text(test_splitter)': {
            'sentences': [{
                'len': 21,
                TEXT_SPAN_FEATURE_NAME: {
                    TEXT_SPAN_START_FEATURE: 0,
                    TEXT_SPAN_END_FEATURE: 21
                }
            }, {
                'len': 23,
                TEXT_SPAN_FEATURE_NAME: {
                    TEXT_SPAN_START_FEATURE: 22,
                    TEXT_SPAN_END_FEATURE: 45
                }
            }]
        }
    }, {
        UUID_COLUMN: b'2' * 16,
        'text': 'b2 [2, 1] first sentence. [2, 1] second sentence.',
        'text(test_splitter)': {
            'sentences': [{
                'len': 24,
                TEXT_SPAN_FEATURE_NAME: {
                    TEXT_SPAN_START_FEATURE: 0,
                    TEXT_SPAN_END_FEATURE: 24
                }
            }, {
                'len': 23,
                TEXT_SPAN_FEATURE_NAME: {
                    TEXT_SPAN_START_FEATURE: 25,
                    TEXT_SPAN_END_FEATURE: 48
                }
            }]
        }
    }]
    assert list(result) == expected_result

  @pytest.mark.parametrize('db_cls', ALL_DBS)
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
      db.select_rows(columns=[('text(test_signal)', 'invalid')])

    with pytest.raises(ValueError, match='Selecting a specific index of a repeated field'):
      db.select_rows(columns=[('text2(test_signal)', 4)])

  @pytest.mark.parametrize('db_cls', ALL_DBS)
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

  @pytest.mark.parametrize('db_cls', ALL_DBS)
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
  def fields(self) -> dict[str, Field]:
    return {'len': Field(dtype=DataType.INT32), 'flen': Field(dtype=DataType.FLOAT32)}

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
  name = 'test_splitter'
  enrichment_type = EnrichmentType.TEXT

  @override
  def fields(self) -> dict[str, Field]:
    return {
        'sentences':
            Field(repeated_field=Field(fields=SpanFields({'len': Field(dtype=DataType.INT32)})))
    }

  @override
  def compute(self,
              data: Optional[Iterable[RichData]] = None,
              keys: Optional[Iterable[bytes]] = None,
              get_embedding_index: Optional[GetEmbeddingIndexFn] = None) -> Iterable[Item]:
    if data is None:
      raise ValueError('Sentence splitter requires text data.')

    for text in data:
      if not isinstance(text, str):
        raise ValueError(f'Expected text to be a string, got {type(text)} instead.')
      sentences = text.split('.')
      yield {
          'sentences': [
              SpanItem(span=(text.index(sentence), text.index(sentence) + len(sentence)),
                       item={'len': len(sentence)}) for sentence in sentences if sentence
          ]
      }


class TestInvalidSignal(Signal):
  name = 'test_invalid_signal'
  enrichment_type = EnrichmentType.TEXT

  @override
  def fields(self) -> dict[str, Field]:
    return {'len': Field(dtype=DataType.INT32)}

  @override
  def compute(
      self,
      data: Optional[Iterable[RichData]] = None,
      keys: Optional[Iterable[bytes]] = None,
      get_embedding_index: Optional[GetEmbeddingIndexFn] = None) -> Iterable[Optional[Item]]:
    # Return an invalid output that doesn't match the input length.
    return []


class ComputeSignalItemsSuite:

  @pytest.mark.parametrize('db_cls', ALL_DBS)
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

    with pytest.raises(ValueError,
                       match='The enriched output and the input data do not have the same length'):
      db.compute_signal_columns(signal=signal, column=('text',))
