"""Tests for the SQLite source."""
import os
import pathlib
import sqlite3

import pytest
from pytest_mock import MockerFixture

from ..schema import schema
from ..source import SourceSchema
from ..sources.sqlite_source import SQLiteSource


@pytest.fixture(autouse=True)
def set_project_path(tmp_path: pathlib.Path, mocker: MockerFixture) -> None:
  # We need to set the project path so extensions like https will be installed in temp dir.
  mocker.patch.dict(os.environ, {'LILAC_PROJECT_DIR': str(tmp_path)})


def test_sqlite(tmp_path: pathlib.Path) -> None:
  db_file = os.path.join(str(tmp_path), 'test.db')
  rows = [{'x': 1, 'y': 'ten'}, {'x': 2, 'y': 'twenty'}, {'x': 3, 'y': 'thirty'}]
  conn = sqlite3.connect(db_file)
  cursor = conn.cursor()
  cursor.execute(
    """
    CREATE TABLE test (
        x INTEGER,
        y TEXT
    )
  """
  )
  # Insert sample data.
  for row in rows:
    cursor.execute('INSERT INTO test (x, y) VALUES (?, ?)', tuple(row.values()))
  conn.commit()
  conn.close()

  source = SQLiteSource(db_file=db_file, table='test')
  source.setup()
  source_schema = source.source_schema()
  assert source_schema == SourceSchema(
    fields=schema({'x': 'int64', 'y': 'string'}).fields, num_items=3
  )

  items = list(source.yield_items())

  assert items == [{'x': 1, 'y': 'ten'}, {'x': 2, 'y': 'twenty'}, {'x': 3, 'y': 'thirty'}]
