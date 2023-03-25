"""Tests implentations of db_dataset."""

import pathlib
from typing import Callable, Iterable, Optional, Type

import pytest
from typing_extensions import override  # type: ignore

from ..embeddings.embedding_index import EmbeddingIndex, GetEmbeddingIndexFn
from ..embeddings.embedding_registry import EmbeddingId
from ..schema import UUID_COLUMN, DataType, EnrichmentType, Field, Item, RichData, Schema
from ..signals.signal import Signal
from ..signals.splitters.splitter import (
    TEXT_SPAN_END_FEATURE,
    TEXT_SPAN_FEATURE_NAME,
    TEXT_SPAN_START_FEATURE,
    SpanFields,
    SpanItem,
)
from .db_dataset import DatasetDB, DatasetManifest, SortOrder
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


class TestSelectRows:

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
  def compute(
      self,
      data: Optional[Iterable[str]] = None,
      keys: Optional[Iterable[bytes]] = None,
      get_embedding_index: Optional[Callable[[EmbeddingId, Iterable[bytes]], EmbeddingIndex]] = None
  ) -> Iterable[Item]:
    if data is None:
      raise ValueError('Sentence splitter requires text data.')

    for text in data:
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


class TestComputeSignalItems:

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
      db.compute_signal_column(signal=signal, column=('text',))

  @pytest.mark.parametrize('db_cls', ALL_DBS)
  def test_compute_signal_column_simple(self, tmp_path: pathlib.Path,
                                        db_cls: Type[DatasetDB]) -> None:
    test_signal = TestSignal()

    db = make_db(db_cls=db_cls,
                 tmp_path=tmp_path,
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

    db.compute_signal_column(signal=test_signal, column='text')

    # Check the enriched dataset manifest has 'text' enriched, but not 'text2'.
    dataset_manifest = db.manifest()
    expected_dataset_manifest = DatasetManifest(
        namespace=TEST_NAMESPACE,
        dataset_name=TEST_DATASET_NAME,
        data_schema=Schema(
            fields={
                UUID_COLUMN:
                    Field(dtype=DataType.BINARY),
                'text':
                    Field(dtype=DataType.STRING),
                'text2':
                    Field(repeated_field=Field(dtype=DataType.STRING)),
                'text.test_signal':
                    Field(fields={
                        'len': Field(dtype=DataType.INT32),
                        'flen': Field(dtype=DataType.FLOAT32)
                    },
                          enriched=True)
            }))
    assert dataset_manifest == expected_dataset_manifest

    db.compute_signal_column(signal=test_signal, column='text2')

    # Check the enriched dataset manifest has both enriched.
    dataset_manifest = db.manifest()
    expected_dataset_manifest = DatasetManifest(
        namespace=TEST_NAMESPACE,
        dataset_name=TEST_DATASET_NAME,
        data_schema=Schema(
            fields={
                UUID_COLUMN:
                    Field(dtype=DataType.BINARY),
                'text':
                    Field(dtype=DataType.STRING),
                'text2':
                    Field(repeated_field=Field(dtype=DataType.STRING)),
                'text.test_signal':
                    Field(fields={
                        'len': Field(dtype=DataType.INT32),
                        'flen': Field(dtype=DataType.FLOAT32)
                    },
                          enriched=True),
                'text2.test_signal':
                    Field(repeated_field=Field(fields={
                        'len': Field(dtype=DataType.INT32),
                        'flen': Field(dtype=DataType.FLOAT32)
                    },
                                               enriched=True),
                          enriched=True)
            }))
    assert dataset_manifest == expected_dataset_manifest

  @pytest.mark.parametrize('db_cls', ALL_DBS)
  def test_compute_signal_column_splits(self, tmp_path: pathlib.Path,
                                        db_cls: Type[DatasetDB]) -> None:

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

    db.compute_signal_column(signal=TestSplitterWithLen(), column='text')

    # Check the enriched dataset manifest.
    dataset_manifest = db.manifest()
    expected_dataset_manifest = DatasetManifest(
        namespace=TEST_NAMESPACE,
        dataset_name=TEST_DATASET_NAME,
        data_schema=Schema(
            fields={
                UUID_COLUMN:
                    Field(dtype=DataType.BINARY),
                'text':
                    Field(dtype=DataType.STRING),
                'text.test_splitter':
                    Field(fields={
                        'sentences':
                            Field(repeated_field=Field(
                                fields={
                                    'len':
                                        Field(dtype=DataType.INT32),
                                    TEXT_SPAN_FEATURE_NAME:
                                        Field(
                                            fields={
                                                TEXT_SPAN_START_FEATURE:
                                                    Field(dtype=DataType.INT32),
                                                TEXT_SPAN_END_FEATURE:
                                                    Field(dtype=DataType.INT32)
                                            })
                                }))
                    },
                          enriched=True),
            }))
    assert dataset_manifest == expected_dataset_manifest
