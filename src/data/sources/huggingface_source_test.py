"""Tests for the pandas source."""
import os
import pathlib

# mypy: disable-error-code="attr-defined"
from datasets import Dataset, Features, Sequence, Value

from ...schema import UUID_COLUMN, DataType, Field, Schema
from .huggingface_source import HF_SPLIT_COLUMN, HuggingFaceDataset
from .source import SourceProcessResult


def test_simple_hf(tmp_path: pathlib.Path) -> None:
  dataset = Dataset.from_list([{'x': 1, 'y': '10'}, {'x': 1, 'y': '10'}])

  dataset_name = os.path.join(tmp_path, 'hf-test-dataset')
  dataset.save_to_disk(dataset_name)

  source = HuggingFaceDataset(dataset_name=dataset_name, load_from_disk=True)

  result = source.process(str(os.path.join(tmp_path, 'data')))

  expected_result = SourceProcessResult(data_schema=Schema(
      fields={
          UUID_COLUMN: Field(dtype=DataType.BINARY),
          HF_SPLIT_COLUMN: Field(dtype=DataType.STRING),
          'x': Field(dtype=DataType.INT64),
          'y': Field(dtype=DataType.STRING),
      }),
                                        num_items=2,
                                        filepaths=[])

  # Validate except for the filepaths, which are not deterministic.
  expected_result.filepaths = result.filepaths
  assert result == expected_result
  assert len(result.filepaths) == 1


def test_simple_hf_sequence(tmp_path: pathlib.Path) -> None:
  dataset = Dataset.from_list([{
      'x': 1,
      'y': [1, 0]
  }, {
      'x': 2,
      'y': [2, 0]
  }],
                              features=Features({
                                  'x': Value(dtype='int64'),
                                  'y': Sequence(feature=Value(dtype='int64'))
                              }))

  dataset_name = os.path.join(tmp_path, 'hf-test-dataset')
  dataset.save_to_disk(dataset_name)

  source = HuggingFaceDataset(dataset_name=dataset_name, load_from_disk=True)

  result = source.process(str(os.path.join(tmp_path, 'data')))

  expected_result = SourceProcessResult(data_schema=Schema(
      fields={
          UUID_COLUMN: Field(dtype=DataType.BINARY),
          HF_SPLIT_COLUMN: Field(dtype=DataType.STRING),
          'x': Field(dtype=DataType.INT64),
          'y': Field(repeated_field=Field(dtype=DataType.INT64)),
      }),
                                        num_items=2,
                                        filepaths=[])

  # Validate except for the filepaths, which are not deterministic.
  expected_result.filepaths = result.filepaths
  assert result == expected_result
  assert len(result.filepaths) == 1
