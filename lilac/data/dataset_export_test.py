"""Implementation-agnostic tests for exporting a dataset."""

import csv
import json
import pathlib
from typing import Iterable, Optional

import numpy as np
import pandas as pd
import pytest
from typing_extensions import override

from ..schema import ROWID, Field, Item, RichData, field
from ..signal import TextSignal, clear_signal_registry, register_signal
from .dataset_test_utils import TestDataMaker


class TestSignal(TextSignal):
  name = 'test_signal'

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

  assert parsed_items == [{
    'text': 'hello',
    'text.test_signal': {
      'len': 5,
      'flen': 5.0
    }
  }, {
    'text': 'everybody',
    'text.test_signal': {
      'len': 9,
      'flen': 9.0
    }
  }]


def test_export_to_csv(make_test_data: TestDataMaker, tmp_path: pathlib.Path) -> None:
  dataset = make_test_data([{'text': 'hello'}, {'text': 'everybody'}])
  dataset.compute_signal(TestSignal(), 'text')

  # Download all columns.
  filepath = tmp_path / 'dataset.csv'
  dataset.to_csv(filepath)

  with open(filepath) as f:
    rows = list(csv.reader(f))

  assert rows == [
    ['text', 'text.test_signal'],
    ['hello', "{'len': 5, 'flen': 5.0}"],
    ['everybody', "{'len': 9, 'flen': 9.0}"],
  ]


def test_export_to_parquet(make_test_data: TestDataMaker, tmp_path: pathlib.Path) -> None:
  dataset = make_test_data([{'text': 'hello'}, {'text': 'everybody'}])
  dataset.compute_signal(TestSignal(), 'text')

  # Download all columns.
  filepath = tmp_path / 'dataset.parquet'
  dataset.to_parquet(filepath)

  df = pd.read_parquet(filepath)
  expected_df = pd.DataFrame([{
    'text': 'hello',
    'text.test_signal': {
      'len': 5,
      'flen': 5.0
    }
  }, {
    'text': 'everybody',
    'text.test_signal': {
      'len': 9,
      'flen': 9.0
    }
  }])
  pd.testing.assert_frame_equal(df, expected_df)


def test_export_to_pandas(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data([{'text': 'hello'}, {'text': 'everybody'}])
  dataset.compute_signal(TestSignal(), 'text')

  # Download all columns.
  df = dataset.to_pandas()
  expected_df = pd.DataFrame([{
    'text': 'hello',
    'text.test_signal': {
      'len': 5,
      'flen': 5.0
    }
  }, {
    'text': 'everybody',
    'text.test_signal': {
      'len': 9,
      'flen': 9.0
    }
  }])
  pd.testing.assert_frame_equal(df, expected_df)

  # Select only some columns, including pseudocolumn rowid.
  df = dataset.to_pandas([ROWID, 'text', 'text.test_signal.flen'])
  expected_df = pd.DataFrame([{
    ROWID: '1',
    'text': 'hello',
    'text.test_signal.flen': np.float32(5.0)
  }, {
    ROWID: '2',
    'text': 'everybody',
    'text.test_signal.flen': np.float32(9.0)
  }])
  pd.testing.assert_frame_equal(df, expected_df)

  # Invalid columns.
  with pytest.raises(ValueError, match="Unable to select path \\('text', 'test_signal2'\\)"):
    dataset.to_pandas(['text', 'text.test_signal2'])
