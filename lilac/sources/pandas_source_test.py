"""Tests for the pandas source."""

import pandas as pd

from ..schema import schema
from ..source import SourceSchema
from .pandas_source import PANDAS_INDEX_COLUMN, PandasSource


def test_simple_dataframe() -> None:
  df = pd.DataFrame.from_records(
    [{'name': 'a', 'age': 1}, {'name': 'b', 'age': 2}, {'name': 'c', 'age': 3}]
  )

  source = PandasSource(df)
  source.setup()

  source_schema = source.source_schema()
  assert source_schema == SourceSchema(
    fields=schema({PANDAS_INDEX_COLUMN: 'int64', 'name': 'string', 'age': 'int64'}).fields,
    num_items=3,
  )

  items = list(source.yield_items())

  assert items == [
    {PANDAS_INDEX_COLUMN: 0, 'name': 'a', 'age': 1},
    {PANDAS_INDEX_COLUMN: 1, 'name': 'b', 'age': 2},
    {PANDAS_INDEX_COLUMN: 2, 'name': 'c', 'age': 3},
  ]


def test_simple_dataframe_with_index() -> None:
  df = pd.DataFrame.from_records(
    [{'name': 'a', 'age': 1}, {'name': 'b', 'age': 2}, {'name': 'c', 'age': 3}],
    index=['id1', 'id2', 'id3'],
  )

  source = PandasSource(df)
  source.setup()

  source_schema = source.source_schema()
  assert source_schema == SourceSchema(
    fields=schema({PANDAS_INDEX_COLUMN: 'string', 'name': 'string', 'age': 'int64'}).fields,
    num_items=3,
  )

  items = list(source.yield_items())

  # The PANDAS_INDEX_COLUMN aligns with the pandas index.
  assert items == [
    {PANDAS_INDEX_COLUMN: 'id1', 'name': 'a', 'age': 1},
    {PANDAS_INDEX_COLUMN: 'id2', 'name': 'b', 'age': 2},
    {PANDAS_INDEX_COLUMN: 'id3', 'name': 'c', 'age': 3},
  ]
