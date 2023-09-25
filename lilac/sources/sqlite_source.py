"""SQLite source."""

import os
import sqlite3
from typing import ClassVar, Iterable, Optional, cast

import duckdb
import pyarrow as pa
from fastapi import APIRouter
from pydantic import Field
from typing_extensions import override

from lilac.utils import file_exists

from ..schema import Item, arrow_schema_to_schema
from ..source import Source, SourceSchema
from .duckdb_utils import duckdb_setup

router = APIRouter()


@router.get('/tables')
def get_tables(db_file: str) -> list[str]:
  """List the table names in sqlite."""
  if not file_exists(db_file) or os.path.isdir(db_file):
    return []
  conn = sqlite3.connect(db_file)
  cursor = conn.cursor()
  cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
  res = [row[0] for row in cursor.fetchall()]
  cursor.close()
  conn.close()
  return res


class SQLiteSource(Source):
  """SQLite data loader."""
  name: ClassVar[str] = 'sqlite'
  router: ClassVar[APIRouter] = router

  db_file: str = Field(title='Database file', description='Path to the database file.')
  table: str = Field(description='Table name to read from.')

  _source_schema: Optional[SourceSchema] = None
  _reader: Optional[pa.RecordBatchReader] = None
  _con: Optional[duckdb.DuckDBPyConnection] = None

  @override
  def setup(self) -> None:
    self._con = duckdb.connect(database=':memory:')
    self._con.install_extension('sqlite')
    self._con.load_extension('sqlite')

    # DuckDB expects s3 protocol: https://duckdb.org/docs/guides/import/s3_import.html.
    db_file = self.db_file.replace('gs://', 's3://')

    self._con.execute(f"""
      {duckdb_setup(self._con)}
      CREATE VIEW t as (SELECT * FROM sqlite_scan('{db_file}', '{self.table}'));
    """)

    res = self._con.execute('SELECT COUNT(*) FROM t').fetchone()
    num_items = cast(tuple[int], res)[0]

    self._reader = self._con.execute('SELECT * from t').fetch_record_batch(rows_per_batch=10_000)
    # Create the source schema in prepare to share it between process and source_schema.
    schema = arrow_schema_to_schema(self._reader.schema)
    self._source_schema = SourceSchema(fields=schema.fields, num_items=num_items)

  @override
  def source_schema(self) -> SourceSchema:
    """Return the source schema."""
    assert self._source_schema is not None
    return self._source_schema

  @override
  def process(self) -> Iterable[Item]:
    """Process the source."""
    if not self._reader or not self._con:
      raise RuntimeError('SQLite source is not initialized.')

    for batch in self._reader:
      yield from batch.to_pylist()

    self._reader.close()
    self._con.close()
