"""Implementation-agnostic tests for exporting a dataset."""

import csv
import json
import pathlib
from datetime import datetime
from typing import ClassVar, Iterable, Iterator, Optional

import numpy as np
import pandas as pd
import pytest
from freezegun import freeze_time
from typing_extensions import override

from ..schema import ROWID, VALUE_KEY, Field, Item, RichData, field
from ..signal import TextSignal, clear_signal_registry, register_signal
from .dataset import DELETED_LABEL_NAME
from .dataset_test_utils import TestDataMaker


class TestSignal(TextSignal):
  name: ClassVar[str] = 'test_signal'

  @override
  def fields(self) -> Field:
    return field(fields={'len': 'int32', 'flen': 'float32'})

  @override
  def compute(self, data: Iterable[RichData]) -> Iterator[Optional[Item]]:
    return ({'len': len(text_content), 'flen': float(len(text_content))} for text_content in data)


@pytest.fixture(scope='module', autouse=True)
def setup_teardown() -> Iterable[None]:
  # Setup.
  clear_signal_registry()
  register_signal(TestSignal)

  yield  # Unit test runs.
  clear_signal_registry()  # Teardown.


def test_export_to_huggingface(make_test_data: TestDataMaker, tmp_path: pathlib.Path) -> None:
  dataset = make_test_data([{'text': 'hello'}, {'text': 'everybody'}])
  dataset.compute_signal(TestSignal(), 'text')

  hf_dataset = dataset.to_huggingface()

  assert list(hf_dataset) == [
    {'text': 'hello'},
    {'text': 'everybody'},
  ]


def test_export_to_huggingface_include_signals(
  make_test_data: TestDataMaker, tmp_path: pathlib.Path
) -> None:
  dataset = make_test_data([{'text': 'hello'}, {'text': 'everybody'}])
  dataset.compute_signal(TestSignal(), 'text')

  hf_dataset = dataset.to_huggingface(include_signals=True)

  assert list(hf_dataset) == [
    {'text': {VALUE_KEY: 'hello', 'test_signal': {'flen': 5.0, 'len': 5}}},
    {'text': {VALUE_KEY: 'everybody', 'test_signal': {'flen': 9.0, 'len': 9}}},
  ]


def test_export_to_huggingface_filters(
  make_test_data: TestDataMaker, tmp_path: pathlib.Path
) -> None:
  dataset = make_test_data([{'text': 'hello'}, {'text': 'everybody'}])
  dataset.compute_signal(TestSignal(), 'text')

  # Download a subset of columns with filter.
  hf_dataset = dataset.to_huggingface(
    columns=['text', 'text.test_signal.flen'],
    filters=[('text.test_signal.len', 'greater', 6)],
    include_signals=True,
  )

  assert list(hf_dataset) == [
    {'text': {VALUE_KEY: 'everybody', 'test_signal': {'flen': 9.0, 'len': 9}}}
  ]

  hf_dataset = dataset.to_huggingface(
    filters=[('text.test_signal.flen', 'less_equal', '5')],
    include_signals=True,
  )

  assert list(hf_dataset) == [
    {'text': {VALUE_KEY: 'hello', 'test_signal': {'flen': 5.0, 'len': 5}}}
  ]


def test_export_to_json(make_test_data: TestDataMaker, tmp_path: pathlib.Path) -> None:
  dataset = make_test_data([{'text': 'hello'}, {'text': 'everybody'}])
  dataset.compute_signal(TestSignal(), 'text')

  # Download all columns.
  filepath = tmp_path / 'dataset.json'
  dataset.to_json(filepath)

  with open(filepath, 'r') as f:
    parsed_items = [json.loads(line) for line in f.readlines()]

  assert parsed_items == [{'text': 'hello'}, {'text': 'everybody'}]

  # Include signals.
  dataset.to_json(filepath, include_signals=True)

  with open(filepath, 'r') as f:
    parsed_items = [json.loads(line) for line in f.readlines()]

  assert parsed_items == [
    {'text': {VALUE_KEY: 'hello', 'test_signal': {'flen': 5.0, 'len': 5}}},
    {'text': {VALUE_KEY: 'everybody', 'test_signal': {'flen': 9.0, 'len': 9}}},
  ]

  # Download a subset of columns with filter.
  filepath = tmp_path / 'dataset2.json'
  dataset.to_json(
    filepath,
    columns=['text', 'text.test_signal.flen'],
    filters=[('text.test_signal.len', 'greater', '6')],
    include_signals=True,
  )

  with open(filepath, 'r') as f:
    parsed_items = [json.loads(line) for line in f.readlines()]

  assert parsed_items == [
    {'text': {VALUE_KEY: 'everybody', 'test_signal': {'flen': 9.0, 'len': 9}}}
  ]

  filepath = tmp_path / 'dataset3.json'
  dataset.to_json(
    filepath, filters=[('text.test_signal.flen', 'less_equal', '5')], include_signals=True
  )

  with open(filepath, 'r') as f:
    parsed_items = [json.loads(line) for line in f.readlines()]

  assert parsed_items == [{'text': {VALUE_KEY: 'hello', 'test_signal': {'flen': 5.0, 'len': 5}}}]


def test_export_to_jsonl(make_test_data: TestDataMaker, tmp_path: pathlib.Path) -> None:
  dataset = make_test_data([{'text': 'hello'}, {'text': 'everybody'}])
  dataset.compute_signal(TestSignal(), 'text')

  # Download all columns.
  filepath = tmp_path / 'dataset.json'
  dataset.to_json(filepath, jsonl=True)

  with open(filepath, 'r') as f:
    parsed_items = [json.loads(line) for line in f.readlines()]

  assert parsed_items == [{'text': 'hello'}, {'text': 'everybody'}]

  # Include signals.
  dataset.to_json(filepath, jsonl=True, include_signals=True)

  with open(filepath, 'r') as f:
    parsed_items = [json.loads(line) for line in f.readlines()]

  assert parsed_items == [
    {'text': {VALUE_KEY: 'hello', 'test_signal': {'flen': 5.0, 'len': 5}}},
    {'text': {VALUE_KEY: 'everybody', 'test_signal': {'flen': 9.0, 'len': 9}}},
  ]

  # Download a subset of columns with filter.
  filepath = tmp_path / 'dataset2.json'
  dataset.to_json(
    filepath,
    jsonl=True,
    columns=['text', 'text.test_signal'],
    filters=[('text.test_signal.len', 'greater', '6')],
    include_signals=True,
  )

  with open(filepath, 'r') as f:
    parsed_items = [json.loads(line) for line in f.readlines()]

  assert parsed_items == [
    {'text': {VALUE_KEY: 'everybody', 'test_signal': {'flen': 9.0, 'len': 9}}}
  ]

  filepath = tmp_path / 'dataset3.json'
  dataset.to_json(
    filepath,
    jsonl=True,
    filters=[('text.test_signal.flen', 'less_equal', '5')],
    include_signals=True,
  )

  with open(filepath, 'r') as f:
    parsed_items = [json.loads(line) for line in f.readlines()]

  assert parsed_items == [{'text': {VALUE_KEY: 'hello', 'test_signal': {'flen': 5.0, 'len': 5}}}]


def test_export_to_csv(make_test_data: TestDataMaker, tmp_path: pathlib.Path) -> None:
  dataset = make_test_data([{'text': 'hello'}, {'text': 'everybody'}])
  dataset.compute_signal(TestSignal(), 'text')

  # Download all columns.
  filepath = tmp_path / 'dataset.csv'
  dataset.to_csv(filepath)

  with open(filepath, 'r') as f:
    rows = list(csv.reader(f))

  assert rows == [
    ['text'],  # Header
    ['hello'],
    ['everybody'],
  ]


def test_export_to_csv_include_signals(
  make_test_data: TestDataMaker, tmp_path: pathlib.Path
) -> None:
  dataset = make_test_data([{'text': 'hello'}, {'text': 'everybody'}])
  dataset.compute_signal(TestSignal(), 'text')

  # Download all columns.
  filepath = tmp_path / 'dataset.csv'
  dataset.to_csv(filepath, include_signals=True)

  with open(filepath, 'r') as f:
    rows = list(csv.reader(f))

  assert rows == [
    ['text'],  # Header
    ["{'__value__': 'hello', 'test_signal': {'len': 5, 'flen': 5.0}}"],
    ["{'__value__': 'everybody', 'test_signal': {'len': 9, 'flen': 9.0}}"],
  ]


def test_export_to_csv_subset_source_columns(
  make_test_data: TestDataMaker, tmp_path: pathlib.Path
) -> None:
  dataset = make_test_data(
    [
      {'text': 'hello', 'age': 4, 'metric': 1},
      {'text': 'everybody', 'age': 5, 'metric': 2},
    ]
  )

  # Download all columns.
  filepath = tmp_path / 'dataset.csv'
  dataset.to_csv(filepath, columns=['age', 'metric'])

  with open(filepath, 'r') as f:
    rows = list(csv.reader(f))

  assert rows == [
    ['age', 'metric'],  # Header
    ['4', '1'],
    ['5', '2'],
  ]


def test_export_to_csv_subset_of_nested_data(
  make_test_data: TestDataMaker, tmp_path: pathlib.Path
) -> None:
  dataset = make_test_data(
    [
      {
        'doc': {
          'title': 'hello',
          'content': 'a',
          'paragraphs': [{'text': 'p1', 'size': 1}, {'text': 'p2', 'size': 2}],
        }
      },
      {
        'doc': {
          'title': 'hello2',
          'content': 'b',
          'paragraphs': [{'text': 'p3', 'size': 3}, {'text': 'p4', 'size': 4}],
        }
      },
    ]
  )

  # Download all columns.
  filepath = tmp_path / 'dataset.csv'
  dataset.to_csv(filepath, columns=['doc.content', 'doc.paragraphs.*.text'])

  with open(filepath, 'r') as f:
    rows = list(csv.reader(f))

  assert rows == [
    ['doc'],  # Header
    ["{'content': 'a', 'paragraphs': [{'text': 'p1'}, {'text': 'p2'}]}"],
    ["{'content': 'b', 'paragraphs': [{'text': 'p3'}, {'text': 'p4'}]}"],
  ]


def test_export_to_parquet(make_test_data: TestDataMaker, tmp_path: pathlib.Path) -> None:
  dataset = make_test_data([{'text': 'hello'}, {'text': 'everybody'}])
  dataset.compute_signal(TestSignal(), 'text')

  # Download all columns.
  filepath = tmp_path / 'dataset.parquet'
  dataset.to_parquet(filepath)

  df = pd.read_parquet(filepath)
  expected_df = pd.DataFrame([{'text': 'hello'}, {'text': 'everybody'}])
  pd.testing.assert_frame_equal(df, expected_df)


def test_export_to_parquet_include_signals(
  make_test_data: TestDataMaker, tmp_path: pathlib.Path
) -> None:
  dataset = make_test_data([{'text': 'hello'}, {'text': 'everybody'}])
  dataset.compute_signal(TestSignal(), 'text')

  # Download all columns.
  filepath = tmp_path / 'dataset.parquet'
  dataset.to_parquet(filepath, include_signals=True)

  df = pd.read_parquet(filepath)
  expected_df = pd.DataFrame(
    [
      {'text': {VALUE_KEY: 'hello', 'test_signal': {'len': 5, 'flen': 5.0}}},
      {'text': {VALUE_KEY: 'everybody', 'test_signal': {'len': 9, 'flen': 9.0}}},
    ]
  )
  pd.testing.assert_frame_equal(df, expected_df)


def test_export_to_pandas(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data([{'text': 'hello'}, {'text': 'everybody'}])
  dataset.compute_signal(TestSignal(), 'text')

  # Download all columns.
  df = dataset.to_pandas()
  expected_df = pd.DataFrame.from_records([{'text': 'hello'}, {'text': 'everybody'}])
  pd.testing.assert_frame_equal(df, expected_df)

  # Download all columns, including signals.
  df = dataset.to_pandas(include_signals=True)
  expected_df = pd.DataFrame.from_records(
    [
      {'text': {VALUE_KEY: 'hello', 'test_signal': {'len': 5, 'flen': 5.0}}},
      {'text': {VALUE_KEY: 'everybody', 'test_signal': {'len': 9, 'flen': 9.0}}},
    ]
  )
  pd.testing.assert_frame_equal(df, expected_df)

  # Select only some columns, including pseudocolumn rowid.
  df = dataset.to_pandas([ROWID, 'text.test_signal.flen'], include_signals=True)
  expected_df = pd.DataFrame(
    [
      {ROWID: '00001', 'text': {'test_signal': {'flen': np.float32(5.0)}}},
      {ROWID: '00002', 'text': {'test_signal': {'flen': np.float32(9.0)}}},
    ]
  )
  pd.testing.assert_frame_equal(df, expected_df)

  # Invalid columns.
  with pytest.raises(ValueError, match="Unable to select path \\('text', 'test_signal2'\\)"):
    dataset.to_pandas(['text', 'text.test_signal2'])


TEST_TIME = datetime(2023, 8, 15, 1, 23, 45)


@freeze_time(TEST_TIME)
def test_label_and_export_by_excluding(
  make_test_data: TestDataMaker, tmp_path: pathlib.Path
) -> None:
  dataset = make_test_data([{'text': 'a'}, {'text': 'b'}, {'text': 'c'}])
  dataset.delete_rows(['00002', '00003'])

  # Download without deleted label.
  filepath = tmp_path / 'dataset.json'
  dataset.to_json(filepath)

  with open(filepath, 'r') as f:
    parsed_items = [json.loads(line) for line in f.readlines()]

  assert parsed_items == [{f'{DELETED_LABEL_NAME}': None, 'text': 'a'}]

  # Include deleted.
  filepath = tmp_path / 'dataset.json'
  dataset.to_json(filepath, include_deleted=True)

  with open(filepath, 'r') as f:
    parsed_items = [json.loads(line) for line in f.readlines()]

  assert parsed_items == [
    {DELETED_LABEL_NAME: None, 'text': 'a'},
    {
      DELETED_LABEL_NAME: {'created': '2023-08-15T01:23:45', 'label': 'true'},
      'text': 'b',
    },
    {
      DELETED_LABEL_NAME: {'created': '2023-08-15T01:23:45', 'label': 'true'},
      'text': 'c',
    },
  ]


def test_include_multiple_labels(make_test_data: TestDataMaker, tmp_path: pathlib.Path) -> None:
  dataset = make_test_data([{'text': 'a'}, {'text': 'b'}, {'text': 'c'}, {'text': 'd'}])
  dataset.add_labels('good', ['00002', '00003'])
  dataset.add_labels('very_good', ['00003', '00004'])

  # Include good and very_good when we export.
  filepath = tmp_path / 'dataset.json'
  dataset.to_json(filepath, columns=['text'], include_labels=['good', 'very_good'])

  with open(filepath, 'r') as f:
    parsed_items = [json.loads(line) for line in f.readlines()]

  parsed_items = sorted(parsed_items, key=lambda x: x['text'])
  assert parsed_items == [{'text': 'b'}, {'text': 'c'}, {'text': 'd'}]


def test_exclude_multiple_labels(make_test_data: TestDataMaker, tmp_path: pathlib.Path) -> None:
  dataset = make_test_data([{'text': 'a'}, {'text': 'b'}, {'text': 'c'}, {'text': 'd'}])
  dataset.add_labels('bad', ['00002'])
  dataset.add_labels('very_bad', ['00002', '00003'])

  # Include good and very_good when we export.
  filepath = tmp_path / 'dataset.json'
  dataset.to_json(filepath, columns=['text'], exclude_labels=['bad', 'very_bad'])

  with open(filepath, 'r') as f:
    parsed_items = [json.loads(line) for line in f.readlines()]

  parsed_items = sorted(parsed_items, key=lambda x: x['text'])
  assert parsed_items == [{'text': 'a'}, {'text': 'd'}]


def test_exclude_trumps_include(make_test_data: TestDataMaker, tmp_path: pathlib.Path) -> None:
  dataset = make_test_data([{'text': 'a'}, {'text': 'b'}, {'text': 'c'}, {'text': 'd'}])
  dataset.add_labels('good', ['00002', '00003', '00004'])
  dataset.add_labels('bad', ['00003', '00004'])

  # Include good and very_good when we export.
  filepath = tmp_path / 'dataset.json'
  dataset.to_json(filepath, columns=['text'], include_labels=['good'], exclude_labels=['bad'])

  with open(filepath, 'r') as f:
    parsed_items = [json.loads(line) for line in f.readlines()]

  assert parsed_items == [{'text': 'b'}]
