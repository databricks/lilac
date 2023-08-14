"""Tests for the JSON source."""
import json
import os
import pathlib

from ..schema import schema
from .json_source import ROW_ID_COLUMN, JSONSource
from .source import SourceSchema


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
    fields=schema({
      ROW_ID_COLUMN: 'int64',
      'x': 'int64',
      'y': 'string'
    }).fields, num_items=2)

  items = list(source.process())

  assert items == [{
    ROW_ID_COLUMN: 0,
    'x': 1,
    'y': 'ten'
  }, {
    ROW_ID_COLUMN: 1,
    'x': 2,
    'y': 'twenty'
  }]


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
    fields=schema({
      ROW_ID_COLUMN: 'int64',
      'x': 'int64',
      'y': 'string'
    }).fields, num_items=2)

  items = list(source.process())

  assert items == [{
    ROW_ID_COLUMN: 0,
    'x': 1,
    'y': 'ten'
  }, {
    ROW_ID_COLUMN: 1,
    'x': 2,
    'y': 'twenty'
  }]
