"""Tests for the CSV source."""
import csv
import os
import pathlib

from ...schema import UUID_COLUMN, schema
from .csv_source import CSVDataset
from .source import SourceSchema


def test_simple_csv(tmp_path: pathlib.Path) -> None:
  csv_rows = [{'x': 1, 'y': 'ten'}, {'x': 2, 'y': 'twenty'}]

  filename = 'test-dataset.csv'
  filepath = os.path.join(tmp_path, filename)
  with open(filepath, 'w') as f:
    writer = csv.DictWriter(f, fieldnames=list(csv_rows[0].keys()))
    writer.writeheader()
    writer.writerows(csv_rows)

  source = CSVDataset(filepaths=[filepath])
  source.prepare()

  source_schema = source.source_schema()
  assert source_schema == SourceSchema(
    fields=schema({
      UUID_COLUMN: 'string',
      'x': 'int64',
      'y': 'string'
    }).fields, num_items=2)

  items = list(source.process())

  assert items == [{
    UUID_COLUMN: '0',
    'x': 1,
    'y': 'ten'
  }, {
    UUID_COLUMN: '1',
    'x': 2,
    'y': 'twenty'
  }]
