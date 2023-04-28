"""Tests for the pandas source."""
import json
import os
import pathlib

from ...schema import UUID_COLUMN, DataType, Field, Schema
from .json_source import JSONDataset
from .source import SourceProcessResult


def test_simple_json(tmp_path: pathlib.Path) -> None:
  json_records = [{'x': 1, 'y': 'ten'}, {'x': 2, 'y': 'twenty'}]

  filename = 'test-dataset.jsonl'
  filepath = os.path.join(tmp_path, filename)
  with open(filepath, 'w') as f:
    f.write(json.dumps(json_records))

  source = JSONDataset(dataset_name='test_dataset', filepaths=[filepath])

  result = source.process(str(os.path.join(tmp_path, 'data')))

  expected_result = SourceProcessResult(
      data_schema=Schema(
          fields={
              UUID_COLUMN: Field(dtype=DataType.STRING),
              'x': Field(dtype=DataType.UINT64),
              'y': Field(dtype=DataType.STRING),
          }),
      num_items=2,
      filepaths=[])

  # Validate except for the filepaths, which are not deterministic.
  expected_result.filepaths = result.filepaths
  assert result == expected_result
  assert len(result.filepaths) == 1


def test_simple_jsonl(tmp_path: pathlib.Path) -> None:
  json_records = [{'x': 1, 'y': 'ten'}, {'x': 2, 'y': 'twenty'}]
  json_lines = [json.dumps(record) + '\n' for record in json_records]

  filename = 'test-dataset.jsonl'
  filepath = os.path.join(tmp_path, filename)
  with open(filepath, 'w') as f:
    f.writelines(json_lines)

  source = JSONDataset(dataset_name='test_dataset', filepaths=[filepath], json_format='records')

  result = source.process(str(os.path.join(tmp_path, 'data')))

  expected_result = SourceProcessResult(
      data_schema=Schema(
          fields={
              UUID_COLUMN: Field(dtype=DataType.STRING),
              'x': Field(dtype=DataType.UINT64),
              'y': Field(dtype=DataType.STRING),
          }),
      num_items=2,
      filepaths=[])

  # Validate except for the filepaths, which are not deterministic.
  expected_result.filepaths = result.filepaths
  assert result == expected_result
  assert len(result.filepaths) == 1
