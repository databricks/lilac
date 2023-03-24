"""Tests implementations of db_dataset_duckdb."""

import os
import pathlib
from typing import Iterable, Optional

import pyarrow.parquet as pq
import pytest
from typing_extensions import override  # type: ignore

from ..embeddings.embedding_index import GetEmbeddingIndexFn
from ..schema import (
    PATH_WILDCARD,
    UUID_COLUMN,
    DataType,
    EnrichmentType,
    Field,
    Item,
    RichData,
    Schema,
)
from ..signals.signal import Signal
from ..signals.signal_registry import clear_signal_registry, register_signal
from ..splitters.splitter_registry import clear_splitter_registry, register_splitter
from ..splitters.text_splitter import (
    SPLITS_FEATURE,
    SPLITS_FIELDS,
    SPLITS_SPAN_END_FEATURE,
    SPLITS_SPAN_START_FEATURE,
    TextSpan,
    TextSplitter,
)
from ..utils import get_dataset_output_dir, open_file
from .db_dataset import DatasetManifest
from .db_dataset_duckdb import (
    DatasetDuckDB,
    SignalManifest,
    signal_manifest_filename,
)
from .db_dataset_test_utils import TEST_DATASET_NAME, TEST_NAMESPACE, make_db


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


@pytest.fixture(scope='module', autouse=True)
def setup_teardown() -> Iterable[None]:
  # Setup.
  register_signal(TestSignal)

  # Unit test runs.
  yield

  # Teardown.
  clear_signal_registry()


def test_compute_signal_columns_simple(tmp_path: pathlib.Path) -> None:
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

  db.compute_signal_columns(signal=test_signal, columns=['text', 'text2'])

  # Check the enriched dataset manifest.
  dataset_manifest = db.manifest()
  expected_dataset_manifest = DatasetManifest(namespace=TEST_NAMESPACE,
                                              dataset_name=TEST_DATASET_NAME,
                                              data_schema=Schema(
                                                  fields={
                                                      UUID_COLUMN:
                                                          Field(dtype=DataType.BINARY),
                                                      'text':
                                                          Field(dtype=DataType.STRING),
                                                      'text2':
                                                          Field(dtype=DataType.STRING),
                                                      'text.test_signal':
                                                          Field(fields={
                                                              'len': Field(dtype=DataType.INT32),
                                                              'flen': Field(dtype=DataType.FLOAT32)
                                                          },
                                                                enriched=True),
                                                      'text2.test_signal':
                                                          Field(fields={
                                                              'len': Field(dtype=DataType.INT32),
                                                              'flen': Field(dtype=DataType.FLOAT32)
                                                          },
                                                                enriched=True)
                                                  }))
  assert dataset_manifest == expected_dataset_manifest

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

  db.compute_signal_columns(signal=test_signal, columns=[('text', PATH_WILDCARD)])

  # Check the enriched dataset manifest.
  manifest = db.manifest()
  expected_manifest = DatasetManifest(
      namespace=TEST_NAMESPACE,
      dataset_name=TEST_DATASET_NAME,
      data_schema=Schema(
          fields={
              UUID_COLUMN:
                  Field(dtype=DataType.BINARY),
              'text':
                  Field(repeated_field=Field(dtype=DataType.STRING)),
              'text.test_signal':
                  Field(repeated_field=Field(fields={
                      'len': Field(dtype=DataType.INT32),
                      'flen': Field(dtype=DataType.FLOAT32)
                  },
                                             enriched=True),
                        enriched=True)
          }))
  assert manifest == expected_manifest

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


class TestSplitter(TextSplitter):
  """Splits documents into sentence by splitting on period."""
  name = 'test_splitter'

  @override
  def split(self, text: str) -> list[TextSpan]:
    sentences = text.split('.')
    return [
        TextSpan(start=text.index(sentence), end=text.index(sentence) + len(sentence))
        for sentence in sentences
        if sentence
    ]


def test_compute_split_column(tmp_path: pathlib.Path) -> None:
  register_splitter(TestSplitter)

  db = make_db(db_cls=DatasetDuckDB,
               tmp_path=tmp_path,
               items=[{
                   UUID_COLUMN: b'1' * 16,
                   'text': '[1, 1] first sentence. [1, 1] second sentence.',
                   'text2': '[1, 2] first sentence. [1, 2] second sentence.',
               }, {
                   UUID_COLUMN: b'2' * 16,
                   'text': 'b2 [2, 1] first sentence. [2, 1] second sentence.',
                   'text2': 'b2 [2, 2] first sentence. [2, 2] second sentence.',
               }],
               schema=Schema(
                   fields={
                       UUID_COLUMN: Field(dtype=DataType.BINARY),
                       'text': Field(dtype=DataType.STRING),
                       'text2': Field(dtype=DataType.STRING),
                   }))

  db.compute_split_column(splitter=TestSplitter(), columns=['text', 'text2'])

  # Check the enriched dataset manifest.
  dataset_manifest = db.manifest()
  expected_dataset_manifest = DatasetManifest(
      namespace=TEST_NAMESPACE,
      dataset_name=TEST_DATASET_NAME,
      data_schema=Schema(
          fields={
              UUID_COLUMN: Field(dtype=DataType.BINARY),
              'text': Field(dtype=DataType.STRING),
              'text2': Field(dtype=DataType.STRING),
              'text.test_splitter': Field(fields=SPLITS_FIELDS, enriched=True),
              'text2.test_splitter': Field(fields=SPLITS_FIELDS, enriched=True)
          }))
  assert dataset_manifest == expected_dataset_manifest

  dataset_path = get_dataset_output_dir(tmp_path, db.namespace, db.dataset_name)

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
          SPLITS_FEATURE: [{
              SPLITS_SPAN_START_FEATURE: 0,
              SPLITS_SPAN_END_FEATURE: 21
          }, {
              SPLITS_SPAN_START_FEATURE: 22,
              SPLITS_SPAN_END_FEATURE: 45
          }]
      }
  }, {
      UUID_COLUMN: b'2' * 16,
      'text': {
          SPLITS_FEATURE: [{
              SPLITS_SPAN_START_FEATURE: 0,
              SPLITS_SPAN_END_FEATURE: 24
          }, {
              SPLITS_SPAN_START_FEATURE: 25,
              SPLITS_SPAN_END_FEATURE: 48
          }]
      }
  }]

  # Make sure the parquet file for 'text2' was written and does not include information about the
  # first column.
  split_parquet_filename = 'text2.test_splitter-00000-of-00001.parquet'
  dataset_path = get_dataset_output_dir(tmp_path, db.namespace, db.dataset_name)

  # Make sure the parquet file for 'text2' was written and does not include information about the
  # first column.
  sentences_parquet_filepath = os.path.join(dataset_path, split_parquet_filename)
  split_items = pq.read_table(sentences_parquet_filepath).to_pylist()

  assert split_items == [{
      UUID_COLUMN: b'1' * 16,
      'text2': {
          SPLITS_FEATURE: [{
              SPLITS_SPAN_START_FEATURE: 0,
              SPLITS_SPAN_END_FEATURE: 21
          }, {
              SPLITS_SPAN_START_FEATURE: 22,
              SPLITS_SPAN_END_FEATURE: 45
          }]
      }
  }, {
      UUID_COLUMN: b'2' * 16,
      'text2': {
          SPLITS_FEATURE: [{
              SPLITS_SPAN_START_FEATURE: 0,
              SPLITS_SPAN_END_FEATURE: 24
          }, {
              SPLITS_SPAN_START_FEATURE: 25,
              SPLITS_SPAN_END_FEATURE: 48
          }]
      }
  }]

  clear_splitter_registry()
