"""Tests for the dict source."""

from ..schema import schema
from ..source import SourceSchema
from .dict_source import DictSource


def test_simple_records() -> None:
  items = [{'x': 1, 'y': 'ten'}, {'x': 2, 'y': 'twenty'}]

  source = DictSource(items)
  source.setup()

  source_schema = source.source_schema()
  assert source_schema == SourceSchema(
    fields=schema({'x': 'int64', 'y': 'string'}).fields, num_items=2
  )

  items = list(source.yield_items())
  assert items == [{'x': 1, 'y': 'ten'}, {'x': 2, 'y': 'twenty'}]


def test_inconsistent_records() -> None:
  items = [{'x': 1, 'y': 'ten'}, {'x': 2, 'y': ['twenty']}, {'x': 3, 'y': {'thirty': True}}]

  source = DictSource(items)
  source.setup()

  source_schema = source.source_schema()
  assert source_schema == SourceSchema(
    fields=schema({'x': 'int64', 'y': 'string'}).fields, num_items=3
  )

  items = list(source.yield_items())
  assert items == [
    {'x': 1, 'y': '"ten"'},
    {'x': 2, 'y': '["twenty"]'},
    {'x': 3, 'y': '{"thirty":true}'},
  ]
