"""Tests implentations of db_dataset."""

import pathlib
from typing import Iterable, Optional, Type

import pytest
from typing_extensions import override  # type: ignore

from ..embeddings.embedding_index import GetEmbeddingIndexFn
from ..schema import UUID_COLUMN, DataType, EnrichmentType, Field, Item, RichData, Schema
from ..signals.signal import Signal
from .db_dataset import DatasetDB, SortOrder
from .db_dataset_duckdb import DatasetDuckDB
from .db_dataset_test_utils import make_db

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
      db.compute_signal_columns(signal=signal, columns=[('text',)])
