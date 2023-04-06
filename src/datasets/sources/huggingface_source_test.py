"""Tests for the pandas source."""
import os
import pathlib

import pandas as pd

# We ignore the types here because "datasets" conflicts with our module.
from datasets import Dataset  # type: ignore

from ...schema import UUID_COLUMN, DataType, Field, Schema
from .huggingface_source import HF_SPLIT_COLUMN, HuggingFaceDataset
from .source import SourceProcessResult


async def test_simple_hf(tmp_path: pathlib.Path) -> None:
  df = pd.DataFrame.from_records([{'x': 1, 'y': '10'}, {'x': 1, 'y': '10'}])
  dataset = Dataset.from_pandas(df)

  dataset_name = os.path.join(tmp_path, 'hf-test-dataset')
  dataset.save_to_disk(dataset_name)

  source = HuggingFaceDataset(dataset_name=dataset_name, load_from_disk=True)

  result = await source.process(str(os.path.join(tmp_path, 'data')))

  expected_result = SourceProcessResult(data_schema=Schema(
      fields={
          UUID_COLUMN: Field(dtype=DataType.BINARY),
          HF_SPLIT_COLUMN: Field(dtype=DataType.STRING),
          'x': Field(dtype=DataType.INT64),
          'y': Field(dtype=DataType.STRING)
      }),
                                        num_items=2,
                                        filepaths=[])

  # Validate except for the filepaths, which are not deterministic.
  expected_result.filepaths = result.filepaths
  assert result == expected_result
  assert len(result.filepaths) == 1
