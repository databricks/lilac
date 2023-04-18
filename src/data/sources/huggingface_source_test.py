"""Tests for the pandas source."""
import os
import pathlib

# mypy: disable-error-code="attr-defined"
from datasets import Dataset, Features, Sequence, Value

from ...schema import UUID_COLUMN, DataType, Field, Schema
from ...test_utils import read_items
from .huggingface_source import HF_SPLIT_COLUMN, HuggingFaceDataset
from .source import SourceProcessResult


def test_hf(tmp_path: pathlib.Path) -> None:
  dataset = Dataset.from_list([{'x': 1, 'y': '10'}, {'x': 2, 'y': '20'}])

  dataset_name = os.path.join(tmp_path, 'hf-test-dataset')
  dataset.save_to_disk(dataset_name)

  source = HuggingFaceDataset(dataset_name=dataset_name, load_from_disk=True)

  result = source.process(str(tmp_path))

  expected_result = SourceProcessResult(data_schema=Schema(
      fields={
          UUID_COLUMN: Field(dtype=DataType.STRING),
          HF_SPLIT_COLUMN: Field(dtype=DataType.STRING),
          'x': Field(dtype=DataType.INT64),
          'y': Field(dtype=DataType.STRING),
      }),
                                        num_items=2,
                                        filepaths=[])

  items = read_items(tmp_path, result.filepaths, expected_result.data_schema)
  assert items == [{
      UUID_COLUMN: items[0][UUID_COLUMN],
      HF_SPLIT_COLUMN: 'default',
      'x': 1,
      'y': '10',
  }, {
      UUID_COLUMN: items[1][UUID_COLUMN],
      HF_SPLIT_COLUMN: 'default',
      'x': 2,
      'y': '20',
  }]


def test_hf_sequence(tmp_path: pathlib.Path) -> None:
  dataset = Dataset.from_list(
      [{
          'scalar': 1,
          'seq': [1, 0],
          'seq_dict': {
              'x': [1, 2, 3],
              'y': ['four', 'five', 'six']
          }
      }, {
          'scalar': 2,
          'seq': [2, 0],
          'seq_dict': {
              'x': [10, 20, 30],
              'y': ['forty', 'fifty', 'sixty']
          }
      }],
      features=Features({
          'scalar': Value(dtype='int64'),
          'seq': Sequence(feature=Value(dtype='int64')),
          'seq_dict': Sequence(feature={
              'x': Value(dtype='int64'),
              'y': Value(dtype='string')
          })
      }))

  dataset_name = os.path.join(tmp_path, 'hf-test-dataset')
  dataset.save_to_disk(dataset_name)

  source = HuggingFaceDataset(dataset_name=dataset_name, load_from_disk=True)

  result = source.process(str(tmp_path))

  expected_result = SourceProcessResult(data_schema=Schema(
      fields={
          UUID_COLUMN:
              Field(dtype=DataType.STRING),
          HF_SPLIT_COLUMN:
              Field(dtype=DataType.STRING),
          'scalar':
              Field(dtype=DataType.INT64),
          'seq':
              Field(repeated_field=Field(dtype=DataType.INT64)),
          'seq_dict':
              Field(
                  fields={
                      'x': Field(repeated_field=Field(dtype=DataType.INT64)),
                      'y': Field(repeated_field=Field(dtype=DataType.STRING)),
                  }),
      }),
                                        num_items=2,
                                        filepaths=[])

  items = read_items(tmp_path, result.filepaths, expected_result.data_schema)
  assert items == [{
      UUID_COLUMN: items[0][UUID_COLUMN],
      HF_SPLIT_COLUMN: 'default',
      'scalar': 1,
      'seq': [1, 0],
      'seq_dict': {
          'x': [1, 2, 3],
          'y': ['four', 'five', 'six']
      }
  }, {
      UUID_COLUMN: items[1][UUID_COLUMN],
      HF_SPLIT_COLUMN: 'default',
      'scalar': 2,
      'seq': [2, 0],
      'seq_dict': {
          'x': [10, 20, 30],
          'y': ['forty', 'fifty', 'sixty']
      }
  }]
