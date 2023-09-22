"""SQLite source."""

import sqlite3
from typing import ClassVar, Iterable, Optional

import duckdb
import pandas as pd
from fastapi import APIRouter
from pydantic import Field
from typing_extensions import override

from ..schema import Item
from ..source import Source, SourceSchema, schema_from_df
from .duckdb_utils import duckdb_setup

router = APIRouter()

DEFAULT_LANGCHAIN_ENDPOINT = 'https://api.smith.langchain.com'


@router.get('/tables')
def get_tables(db_file: str) -> list[str]:
  """List the table names in sqlite."""
  conn = sqlite3.connect(db_file)
  cursor = conn.cursor()
  sql_query = "SELECT name FROM sqlite_master WHERE type='table';"
  cursor.execute(sql_query)
  return [row[0] for row in cursor.fetchall()]


class SQLiteSource(Source):
  """SQLite data loader."""
  name: ClassVar[str] = 'sqlite'
  router: ClassVar[APIRouter] = router

  db_file: str = Field(description='The path to the database file.')
  table: str = Field(description='The table name to read from.')

  _source_schema: Optional[SourceSchema] = None
  _df: Optional[pd.DataFrame] = None

  @override
  def setup(self) -> None:
    con = duckdb.connect(database=':memory:')
    con.install_extension('sqlite')
    con.load_extension('sqlite')

    # DuckDB expects s3 protocol: https://duckdb.org/docs/guides/import/s3_import.html.
    db_file = self.db_file.replace('gs://', 's3://')

    self._df = con.execute(f"""
      {duckdb_setup(con)}
      SELECT * FROM sqlite_scan('{db_file}', '{self.table}');
    """).df()
    for column_name in self._df.columns:
      self._df.rename(columns={column_name: column_name}, inplace=True)

    # Create the source schema in prepare to share it between process and source_schema.
    self._source_schema = schema_from_df(self._df, LINE_NUMBER_COLUMN)

  @override
  def source_schema(self) -> SourceSchema:
    """Return the source schema."""
    assert self._source_schema is not None
    return self._source_schema

  @override
  def process(self) -> Iterable[Item]:
    """Process the source upload request."""
    if self._df is None:
      raise RuntimeError('CSV source is not initialized.')

    cols = self._df.columns.tolist()
    yield from ({
      LINE_NUMBER_COLUMN: idx,
      **dict(zip(cols, item_vals)),
    } for idx, *item_vals in self._df.itertuples())
