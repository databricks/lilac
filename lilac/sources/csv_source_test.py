"""Tests for the CSV source."""
import csv
import os
import pathlib

import pytest
from pytest_mock import MockerFixture

from ..schema import schema
from ..source import SourceSchema
from ..test_utils import retrieve_parquet_rows
from .csv_source import LINE_NUMBER_COLUMN, CSVSource


@pytest.fixture(autouse=True)
def set_project_path(tmp_path: pathlib.Path, mocker: MockerFixture) -> None:
  # We need to set the project path so extensions like https will be installed in temp dir.
  mocker.patch.dict(os.environ, {'LILAC_PROJECT_DIR': str(tmp_path)})


def test_csv(tmp_path: pathlib.Path) -> None:
  csv_rows = [{'x': 1, 'y': 'ten'}, {'x': 2, 'y': 'twenty'}, {'x': 3, 'y': 'thirty'}]

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
    fields=schema({LINE_NUMBER_COLUMN: 'int64', 'x': 'int64', 'y': 'string'}).fields, num_items=3
  )

  manifest = source.load_to_parquet(str(tmp_path), task_step_id=None)
  items = retrieve_parquet_rows(tmp_path, manifest)

  assert items == [
    {LINE_NUMBER_COLUMN: 1, 'x': 1, 'y': 'ten'},
    {LINE_NUMBER_COLUMN: 2, 'x': 2, 'y': 'twenty'},
    {LINE_NUMBER_COLUMN: 3, 'x': 3, 'y': 'thirty'},
  ]


def test_csv_multifile(tmp_path: pathlib.Path) -> None:
  csv_rows = [{'x': 1, 'y': 'ten'}, {'x': 2, 'y': 'twenty'}, {'x': 3, 'y': 'thirty'}]

  filepaths = []
  for i in range(3):
    filename = f'test-dataset-{i}.csv'
    filepath = os.path.join(tmp_path, filename)
    with open(filepath, 'w') as f:
      writer = csv.DictWriter(f, fieldnames=list(csv_rows[0].keys()))
      writer.writeheader()
      writer.writerows(csv_rows)
    filepaths.append(filepath)

  source = CSVSource(filepaths=filepaths)
  source.setup()

  source_schema = source.source_schema()
  assert source_schema == SourceSchema(
    fields=schema({LINE_NUMBER_COLUMN: 'int64', 'x': 'int64', 'y': 'string'}).fields, num_items=9
  )

  manifest = source.load_to_parquet(str(tmp_path), task_step_id=None)
  items = retrieve_parquet_rows(tmp_path, manifest)

  assert len(items) == 9
