"""Tests for the JSON source."""
import json
import os
import pathlib

import pytest
from pytest_mock import MockerFixture

from ..schema import schema
from ..source import SourceSchema
from ..test_utils import retrieve_parquet_rows
from .json_source import JSONSource


@pytest.fixture(autouse=True)
def set_project_path(tmp_path: pathlib.Path, mocker: MockerFixture) -> None:
  # We need to set the project path so extensions like https will be installed in temp dir.
  mocker.patch.dict(os.environ, {'LILAC_PROJECT_DIR': str(tmp_path)})


def test_simple_json(tmp_path: pathlib.Path) -> None:
  json_records = [{'x': 1, 'y': 'ten'}, {'x': 2, 'y': 'twenty'}]

  filename = 'test-dataset.jsonl'
  filepath = os.path.join(tmp_path, filename)
  with open(filepath, 'w') as f:
    f.write(json.dumps(json_records))

  source = JSONSource(filepaths=[filepath])
  source.setup()

  source_schema = source.source_schema()
  assert source_schema == SourceSchema(
    fields=schema({'x': 'int64', 'y': 'string'}).fields, num_items=2
  )

  manifest = source.load_to_parquet(str(tmp_path), task_step_id=None)
  items = retrieve_parquet_rows(tmp_path, manifest)

  assert items == [{'x': 1, 'y': 'ten'}, {'x': 2, 'y': 'twenty'}]


def test_simple_jsonl(tmp_path: pathlib.Path) -> None:
  json_records = [{'x': 1, 'y': 'ten'}, {'x': 2, 'y': 'twenty'}]
  json_lines = [json.dumps(record) + '\n' for record in json_records]

  filename = 'test-dataset.jsonl'
  filepath = os.path.join(tmp_path, filename)
  with open(filepath, 'w') as f:
    f.writelines(json_lines)

  source = JSONSource(filepaths=[filepath])
  source.setup()

  source_schema = source.source_schema()

  assert source_schema == SourceSchema(
    fields=schema({'x': 'int64', 'y': 'string'}).fields, num_items=2
  )

  manifest = source.load_to_parquet(str(tmp_path), task_step_id=None)
  items = retrieve_parquet_rows(tmp_path, manifest)

  assert items == [{'x': 1, 'y': 'ten'}, {'x': 2, 'y': 'twenty'}]


def test_sampling_jsonl(tmp_path: pathlib.Path) -> None:
  json_records = [{'x': 1, 'y': 'ten'}, {'x': 2, 'y': 'twenty'}, {'x': 3, 'y': 'thirty'}]
  json_lines = [json.dumps(record) + '\n' for record in json_records]

  filename = 'test-dataset.jsonl'
  filepath = os.path.join(tmp_path, filename)
  with open(filepath, 'w') as f:
    f.writelines(json_lines)

  source = JSONSource(filepaths=[filepath], sample_size=2)
  source.setup()

  source_schema = source.source_schema()
  assert source_schema == SourceSchema(
    fields=schema({'x': 'int64', 'y': 'string'}).fields, num_items=2
  )

  manifest = source.load_to_parquet(str(tmp_path), task_step_id=None)
  items = retrieve_parquet_rows(tmp_path, manifest)
  assert len(items) == 2


def test_sampling_greater_than_dataset(tmp_path: pathlib.Path) -> None:
  json_records = [{'x': 1, 'y': 'ten'}, {'x': 2, 'y': 'twenty'}, {'x': 3, 'y': 'thirty'}]
  json_lines = [json.dumps(record) + '\n' for record in json_records]

  filename = 'test-dataset.jsonl'
  filepath = os.path.join(tmp_path, filename)
  with open(filepath, 'w') as f:
    f.writelines(json_lines)

  source = JSONSource(filepaths=[filepath], sample_size=4)
  source.setup()

  source_schema = source.source_schema()
  assert source_schema == SourceSchema(
    fields=schema({'x': 'int64', 'y': 'string'}).fields, num_items=3
  )

  manifest = source.load_to_parquet(str(tmp_path), task_step_id=None)
  items = retrieve_parquet_rows(tmp_path, manifest)
  assert len(items) == 3
