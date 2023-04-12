"""Tests for the pandas source."""
import pathlib

import pandas as pd

from ...schema import UUID_COLUMN, DataType, Field, Schema
from .pandas_source import PandasDataset
from .source import SourceProcessResult


def test_simple_dataframe(tmp_path: pathlib.Path) -> None:
  df = pd.DataFrame({'name': ['a', 'b', 'c'], 'age': [1, 2, 3]})
  source = PandasDataset(df)

  result = source.process(str(tmp_path))

  expected_result = SourceProcessResult(data_schema=Schema(
      fields={
          UUID_COLUMN: Field(dtype=DataType.BINARY),
          'name': Field(dtype=DataType.STRING),
          'age': Field(dtype=DataType.INT64)
      }),
                                        num_items=3,
                                        filepaths=[])

  # Validate except for the filepaths, which are not deterministic.
  expected_result.filepaths = result.filepaths
  assert result == expected_result
  assert len(result.filepaths) == 1
