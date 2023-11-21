"""Implementation-agnostic tests for exporting a dataset."""

import csv
import json
import pathlib
from datetime import datetime
from typing import ClassVar, Iterable, Optional

import numpy as np
import pandas as pd
import pytest
from freezegun import freeze_time
from typing_extensions import override

from ..schema import ROWID, Field, Item, RichData, field
from ..signal import TextSignal, clear_signal_registry, register_signal
from .dataset_test_utils import TestDataMaker


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
  clear_signal_registry()
  register_signal(TestSignal)

  yield  # Unit test runs.
  clear_signal_registry()  # Teardown.


def test_export_to_json(make_test_data: TestDataMaker, tmp_path: pathlib.Path) -> None:
  dataset = make_test_data([{'text': 'hello'}, {'text': 'everybody'}])
  dataset.compute_signal(TestSignal(), 'text')

  # Download all columns.
  filepath = tmp_path / 'dataset.json'
  dataset.to_json(filepath)

  with open(filepath) as f:
    parsed_items = [json.loads(line) for line in f.readlines()]

  assert parsed_items == [
    {'text': 'hello', 'text.test_signal.len': 5, 'text.test_signal.flen': 5.0},
    {'text': 'everybody', 'text.test_signal.len': 9, 'text.test_signal.flen': 9.0},
  ]

  # Download a subset of columns with filter.
  filepath = tmp_path / 'dataset2.json'
  dataset.to_json(
    filepath,
    columns=['text', 'text.test_signal.flen'],
    filters=[('text.test_signal.len', 'greater', '6')],
  )

  with open(filepath) as f:
    parsed_items = [json.loads(line) for line in f.readlines()]

  assert parsed_items == [{'text': 'everybody', 'text.test_signal.flen': 9.0}]

  filepath = tmp_path / 'dataset3.json'
  dataset.to_json(filepath, filters=[('text.test_signal.flen', 'less_equal', '5')])

  with open(filepath) as f:
    parsed_items = [json.loads(line) for line in f.readlines()]

  assert parsed_items == [
    {'text': 'hello', 'text.test_signal.len': 5, 'text.test_signal.flen': 5.0}
  ]


def test_export_to_csv(make_test_data: TestDataMaker, tmp_path: pathlib.Path) -> None:
  dataset = make_test_data([{'text': 'hello'}, {'text': 'everybody'}])
  dataset.compute_signal(TestSignal(), 'text')

  # Download all columns.
  filepath = tmp_path / 'dataset.csv'
  dataset.to_csv(filepath)

  with open(filepath) as f:
    rows = list(csv.reader(f))

  assert rows == [
    ['text', 'text.test_signal.len', 'text.test_signal.flen'],
    ['hello', '5', '5.0'],
    ['everybody', '9', '9.0'],
  ]


def test_export_to_parquet(make_test_data: TestDataMaker, tmp_path: pathlib.Path) -> None:
  dataset = make_test_data([{'text': 'hello'}, {'text': 'everybody'}])
  dataset.compute_signal(TestSignal(), 'text')

  # Download all columns.
  filepath = tmp_path / 'dataset.parquet'
  dataset.to_parquet(filepath)

  df = pd.read_parquet(filepath)
  expected_df = pd.DataFrame(
    [
      {
        'text': 'hello',
        'text.test_signal.len': 5,
        'text.test_signal.flen': 5.0,
      },
      {
        'text': 'everybody',
        'text.test_signal.len': 9,
        'text.test_signal.flen': 9.0,
      },
    ]
  )
  pd.testing.assert_frame_equal(df, expected_df)


def test_export_to_pandas(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data([{'text': 'hello'}, {'text': 'everybody'}])
  dataset.compute_signal(TestSignal(), 'text')

  # Download all columns.
  df = dataset.to_pandas()
  expected_df = pd.DataFrame(
    [
      {
        'text': 'hello',
        'text.test_signal.len': 5,
        'text.test_signal.flen': 5.0,
      },
      {
        'text': 'everybody',
        'text.test_signal.len': 9,
        'text.test_signal.flen': 9.0,
      },
    ]
  )
  pd.testing.assert_frame_equal(df, expected_df)

  # Select only some columns, including pseudocolumn rowid.
  df = dataset.to_pandas([ROWID, 'text', 'text.test_signal.flen'])
  expected_df = pd.DataFrame(
    [
      {ROWID: '1', 'text': 'hello', 'text.test_signal.flen': np.float64(5.0)},
      {ROWID: '2', 'text': 'everybody', 'text.test_signal.flen': np.float64(9.0)},
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
  dataset.add_labels('delete', ['2', '3'])

  # Download all, except the 'deleted' label.
  filepath = tmp_path / 'dataset.json'
  dataset.to_json(filepath, exclude_labels=['delete'])

  with open(filepath) as f:
    parsed_items = [json.loads(line) for line in f.readlines()]

  assert parsed_items == [{'delete.created': None, 'delete.label': None, 'text': 'a'}]

  # Download only the 'deleted' label.
  filepath = tmp_path / 'dataset.json'
  dataset.to_json(filepath, include_labels=['delete'])

  with open(filepath) as f:
    parsed_items = [json.loads(line) for line in f.readlines()]

  assert parsed_items == [
    {'delete.created': str(TEST_TIME), 'delete.label': 'true', 'text': 'b'},
    {'delete.created': str(TEST_TIME), 'delete.label': 'true', 'text': 'c'},
  ]


def test_include_multiple_labels(make_test_data: TestDataMaker, tmp_path: pathlib.Path) -> None:
  dataset = make_test_data([{'text': 'a'}, {'text': 'b'}, {'text': 'c'}, {'text': 'd'}])
  dataset.add_labels('good', ['2', '3'])
  dataset.add_labels('very_good', ['3', '4'])

  # Include good and very_good when we export.
  filepath = tmp_path / 'dataset.json'
  dataset.to_json(filepath, columns=['text'], include_labels=['good', 'very_good'])

  with open(filepath) as f:
    parsed_items = [json.loads(line) for line in f.readlines()]

  parsed_items = sorted(parsed_items, key=lambda x: x['text'])
  assert parsed_items == [{'text': 'b'}, {'text': 'c'}, {'text': 'd'}]


def test_exclude_multiple_labels(make_test_data: TestDataMaker, tmp_path: pathlib.Path) -> None:
  dataset = make_test_data([{'text': 'a'}, {'text': 'b'}, {'text': 'c'}, {'text': 'd'}])
  dataset.add_labels('bad', ['2'])
  dataset.add_labels('very_bad', ['2', '3'])

  # Include good and very_good when we export.
  filepath = tmp_path / 'dataset.json'
  dataset.to_json(filepath, columns=['text'], exclude_labels=['bad', 'very_bad'])

  with open(filepath) as f:
    parsed_items = [json.loads(line) for line in f.readlines()]

  parsed_items = sorted(parsed_items, key=lambda x: x['text'])
  assert parsed_items == [{'text': 'a'}, {'text': 'd'}]


def test_exclude_trumps_include(make_test_data: TestDataMaker, tmp_path: pathlib.Path) -> None:
  dataset = make_test_data([{'text': 'a'}, {'text': 'b'}, {'text': 'c'}, {'text': 'd'}])
  dataset.add_labels('good', ['2', '3', '4'])
  dataset.add_labels('bad', ['3', '4'])

  # Include good and very_good when we export.
  filepath = tmp_path / 'dataset.json'
  dataset.to_json(filepath, columns=['text'], include_labels=['good'], exclude_labels=['bad'])

  with open(filepath) as f:
    parsed_items = [json.loads(line) for line in f.readlines()]

  assert parsed_items == [{'text': 'b'}]
