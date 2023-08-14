"""Tests for the CSV source."""
import csv
import os
import pathlib

from ..schema import schema
from .csv_source import LINE_NUMBER_COLUMN, CSVSource
from .source import SourceSchema


def test_csv(tmp_path: pathlib.Path) -> None:
  csv_rows = [{'x': 1, 'y': 'ten'}, {'x': 2, 'y': 'twenty'}]

  filename = 'test-dataset.csv'
  filepath = os.path.join(tmp_path, filename)
  with open(filepath, 'w') as f:
    writer = csv.DictWriter(f, fieldnames=list(csv_rows[0].keys()))
    writer.writeheader()
    writer.writerows(csv_rows)

  source = CSVSource(filepaths=[filepath])
  source.setup()

  source_schema = source.source_schema()
  assert source_schema == SourceSchema(
    fields=schema({
      LINE_NUMBER_COLUMN: 'int64',
      'x': 'int64',
      'y': 'string'
    }).fields, num_items=2)

  items = list(source.process())

  assert items == [{
    LINE_NUMBER_COLUMN: 0,
    'x': 1,
    'y': 'ten'
  }, {
    LINE_NUMBER_COLUMN: 1,
    'x': 2,
    'y': 'twenty'
  }]
