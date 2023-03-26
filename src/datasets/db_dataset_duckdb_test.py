"""Tests implementations of db_dataset_duckdb."""

import os
import pathlib
from typing import Iterable

import pyarrow.parquet as pq
import pytest

from ..schema import (
    PATH_WILDCARD,
    UUID_COLUMN,
    DataType,
    Field,
    Schema,
)
from ..signals.signal_registry import clear_signal_registry, register_signal
from ..signals.splitters.splitter import (
    TEXT_SPAN_END_FEATURE,
    TEXT_SPAN_FEATURE_NAME,
    TEXT_SPAN_START_FEATURE,
)
from ..utils import get_dataset_output_dir, open_file
from .db_dataset_duckdb import (
    DatasetDuckDB,
    SignalManifest,
    signal_manifest_filename,
)
from .db_dataset_test import TestSignal, TestSplitterWithLen
from .db_dataset_test_utils import make_db


@pytest.fixture(scope='module', autouse=True)
def setup_teardown() -> Iterable[None]:
  # Setup.
  register_signal(TestSignal)
  register_signal(TestSplitterWithLen)

  # Unit test runs.
  yield

  # Teardown.
  clear_signal_registry()


def test_compute_signal_column_simple(tmp_path: pathlib.Path) -> None:
  test_signal = TestSignal()

  db = make_db(db_cls=DatasetDuckDB,
               tmp_path=tmp_path,
               items=[{
                   UUID_COLUMN: b'1' * 16,
                   'text': 'hello',
                   'text2': 'hello2',
               }, {
                   UUID_COLUMN: b'2' * 16,
                   'text': 'hello world',
                   'text2': 'hello world2',
               }],
               schema=Schema(
                   fields={
                       UUID_COLUMN: Field(dtype=DataType.BINARY),
                       'text': Field(dtype=DataType.STRING),
                       'text2': Field(dtype=DataType.STRING),
                   }))

  db.compute_signal_column(signal=test_signal, column='text')

  dataset_path = get_dataset_output_dir(tmp_path, db.namespace, db.dataset_name)

  # Make sure the signal manifest for 'text' is correct.
  expected_signal_schema = Schema(
      fields={
          UUID_COLUMN:
              Field(dtype=DataType.BINARY),
          'text':
              Field(fields={
                  'len': Field(dtype=DataType.INT32),
                  'flen': Field(dtype=DataType.FLOAT32)
              },
                    enriched=True),
      })

  text_parquet_filename = 'text.test_signal-00000-of-00001.parquet'
  expected_manifest = SignalManifest(files=[text_parquet_filename],
                                     data_schema=expected_signal_schema,
                                     signal=test_signal,
                                     enriched_path=('text',))
  manifest_path = os.path.join(dataset_path, signal_manifest_filename('text', test_signal.name))
  with open_file(manifest_path) as f:
    signal_manifest = SignalManifest.parse_raw(f.read())
    assert signal_manifest == expected_manifest

  # Make sure the parquet file for 'text' was written and does not include information about the
  # second column.
  text_stats_text_filepath = os.path.join(dataset_path, text_parquet_filename)
  signal_items = pq.read_table(text_stats_text_filepath).to_pylist()

  assert signal_items == [{
      UUID_COLUMN: b'1' * 16,
      'text': {
          'len': len('hello'),
          'flen': float(len('hello'))
      }
  }, {
      UUID_COLUMN: b'2' * 16,
      'text': {
          'len': len('hello world'),
          'flen': float(len('hello world'))
      }
  }]

  # Add text2 column now.
  db.compute_signal_column(signal=test_signal, column='text2')

  # Make sure the signal manifest for 'text2' is correct.
  expected_signal_schema = Schema(
      fields={
          UUID_COLUMN:
              Field(dtype=DataType.BINARY),
          'text2':
              Field(fields={
                  'len': Field(dtype=DataType.INT32),
                  'flen': Field(dtype=DataType.FLOAT32)
              },
                    enriched=True),
      })
  text2_parquet_filename = 'text2.test_signal-00000-of-00001.parquet'
  expected_manifest = SignalManifest(files=[text2_parquet_filename],
                                     data_schema=expected_signal_schema,
                                     signal=test_signal,
                                     enriched_path=('text2',))
  manifest_path = os.path.join(dataset_path, signal_manifest_filename('text2', test_signal.name))
  with open_file(manifest_path) as f:
    signal_manifest = SignalManifest.parse_raw(f.read())
    assert signal_manifest == expected_manifest

  # Make sure the parquet file for 'text2' was written and does not include information about the
  # first column.
  text_stats_text2_filepath = os.path.join(dataset_path, text2_parquet_filename)
  signal_items = pq.read_table(text_stats_text2_filepath).to_pylist()

  assert signal_items == [{
      UUID_COLUMN: b'1' * 16,
      'text2': {
          'len': len('hello2'),
          'flen': float(len('hello2'))
      }
  }, {
      UUID_COLUMN: b'2' * 16,
      'text2': {
          'len': len('hello world2'),
          'flen': float(len('hello world2'))
      }
  }]


def test_compute_signal_columns_repeated(tmp_path: pathlib.Path) -> None:
  test_signal = TestSignal()

  db = make_db(db_cls=DatasetDuckDB,
               tmp_path=tmp_path,
               items=[{
                   UUID_COLUMN: b'1' * 16,
                   'text': ['hello', 'hello hello'],
               }, {
                   UUID_COLUMN: b'2' * 16,
                   'text': ['hello2', 'hello2 hello2'],
               }],
               schema=Schema(
                   fields={
                       UUID_COLUMN: Field(dtype=DataType.BINARY),
                       'text': Field(repeated_field=Field(dtype=DataType.STRING)),
                   }))

  db.compute_signal_column(signal=test_signal, column=('text', PATH_WILDCARD))

  text_parquet_filename = 'text.*.test_signal-00000-of-00001.parquet'
  dataset_path = get_dataset_output_dir(tmp_path, db.namespace, db.dataset_name)

  # Make sure the parquet file for 'text' was written and does not include information about the
  # second column.
  text_stats_text_filepath = os.path.join(dataset_path, text_parquet_filename)
  signal_items = pq.read_table(text_stats_text_filepath).to_pylist()

  assert signal_items == [{
      UUID_COLUMN:
          b'1' * 16,
      'text': [{
          'len': len('hello'),
          'flen': float(len('hello'))
      }, {
          'len': len('hello hello'),
          'flen': float(len('hello hello'))
      }]
  }, {
      UUID_COLUMN:
          b'2' * 16,
      'text': [{
          'len': len('hello2'),
          'flen': float(len('hello2'))
      }, {
          'len': len('hello2 hello2'),
          'flen': float(len('hello2 hello2'))
      }]
  }]


def test_compute_split(tmp_path: pathlib.Path) -> None:

  db = make_db(db_cls=DatasetDuckDB,
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

  # Make sure the parquet file for 'text' was written and does not include information about the
  # second column.
  split_parquet_filename = 'text.test_splitter-00000-of-00001.parquet'
  dataset_path = get_dataset_output_dir(tmp_path, db.namespace, db.dataset_name)

  # Make sure the parquet file for 'text' was written and does not include information about the
  # second column.
  sentences_parquet_filepath = os.path.join(dataset_path, split_parquet_filename)
  split_items = pq.read_table(sentences_parquet_filepath).to_pylist()

  assert split_items == [{
      UUID_COLUMN: b'1' * 16,
      'text': {
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
      'text': {
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
