"""Implementation-agnostic tests for exporting a dataset."""

import csv
import json
import pathlib

import pandas as pd

from ..schema import UUID_COLUMN
from .dataset_test_utils import TestDataMaker


def test_export_to_json(make_test_data: TestDataMaker, tmp_path: pathlib.Path) -> None:
  dataset = make_test_data([{
    UUID_COLUMN: '1',
    'text': 'hello'
  }, {
    UUID_COLUMN: '2',
    'text': 'everybody'
  }])
  filepath = tmp_path / 'dataset.json'
  dataset.to_json(filepath)

  with open(filepath) as f:
    parsed_items = [json.loads(line) for line in f.readlines()]

  assert parsed_items == [{
    UUID_COLUMN: '1',
    'text': 'hello'
  }, {
    UUID_COLUMN: '2',
    'text': 'everybody'
  }]


def test_export_to_csv(make_test_data: TestDataMaker, tmp_path: pathlib.Path) -> None:
  dataset = make_test_data([{
    UUID_COLUMN: '1',
    'text': 'hello'
  }, {
    UUID_COLUMN: '2',
    'text': 'everybody'
  }])
  filepath = tmp_path / 'dataset.csv'
  dataset.to_csv(filepath)

  with open(filepath) as f:
    rows = list(csv.reader(f))

  assert rows == [[UUID_COLUMN, 'text'], ['1', 'hello'], ['2', 'everybody']]


def test_export_to_parquet(make_test_data: TestDataMaker, tmp_path: pathlib.Path) -> None:
  dataset = make_test_data([{
    UUID_COLUMN: '1',
    'text': 'hello'
  }, {
    UUID_COLUMN: '2',
    'text': 'everybody'
  }])
  filepath = tmp_path / 'dataset.parquet'
  dataset.to_parquet(filepath)

  df = pd.read_parquet(filepath)
  expected_df = pd.DataFrame([{
    UUID_COLUMN: '1',
    'text': 'hello'
  }, {
    UUID_COLUMN: '2',
    'text': 'everybody'
  }])
  pd.testing.assert_frame_equal(df, expected_df)


def test_export_to_pandas(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data([{
    UUID_COLUMN: '1',
    'text': 'hello'
  }, {
    UUID_COLUMN: '2',
    'text': 'everybody'
  }])

  df = dataset.to_pandas()
  expected_df = pd.DataFrame([{
    UUID_COLUMN: '1',
    'text': 'hello'
  }, {
    UUID_COLUMN: '2',
    'text': 'everybody'
  }])
  pd.testing.assert_frame_equal(df, expected_df)
