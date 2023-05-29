"""Tests for the pandas source."""

import pandas as pd

from ...schema import UUID_COLUMN, schema
from .pandas_source import PandasDataset
from .source import SourceSchema


def test_simple_dataframe() -> None:
  df = pd.DataFrame.from_records([{
    'name': 'a',
    'age': 1
  }, {
    'name': 'b',
    'age': 2
  }, {
    'name': 'c',
    'age': 3
  }])

  source = PandasDataset(df)

  source = PandasDataset(df)
  source.prepare()

  source_schema = source.source_schema()
  assert source_schema == SourceSchema(
    fields=schema({
      UUID_COLUMN: 'string',
      'name': 'string',
      'age': 'int64'
    }).fields, num_items=3)

  items = list(source.process())

  assert items == [{
    UUID_COLUMN: '0',
    'name': 'a',
    'age': 1
  }, {
    UUID_COLUMN: '1',
    'name': 'b',
    'age': 2
  }, {
    UUID_COLUMN: '2',
    'name': 'c',
    'age': 3
  }]


def test_simple_dataframe_with_index() -> None:
  df = pd.DataFrame.from_records([{
    'name': 'a',
    'age': 1
  }, {
    'name': 'b',
    'age': 2
  }, {
    'name': 'c',
    'age': 3
  }],
                                 index=['id1', 'id2', 'id3'])

  source = PandasDataset(df)
  source.prepare()

  source_schema = source.source_schema()
  assert source_schema == SourceSchema(
    fields=schema({
      UUID_COLUMN: 'string',
      'name': 'string',
      'age': 'int64'
    }).fields, num_items=3)

  items = list(source.process())

  # The UUID_COLUMN aligns with the pandas index.
  assert items == [{
    UUID_COLUMN: 'id1',
    'name': 'a',
    'age': 1
  }, {
    UUID_COLUMN: 'id2',
    'name': 'b',
    'age': 2
  }, {
    UUID_COLUMN: 'id3',
    'name': 'c',
    'age': 3
  }]
