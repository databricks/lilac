"""Utilities for working with splitters."""

from ...schema import (
    TEXT_SPAN_END_FEATURE,
    TEXT_SPAN_START_FEATURE,
    DataType,
    Field,
    Item,
)

TextSpanOld = tuple[int, int]


def TextSpan(start: int, end: int) -> Item:
  """Return the span item from start and end."""
  return {TEXT_SPAN_START_FEATURE: start, TEXT_SPAN_END_FEATURE: end}


def SpanItemOld(span: TextSpanOld, item: Item = {}) -> Item:
  """Return the span item from an item."""
  # Add the span dictionary to the item.
  start, end = span
  return {**item, '__textspan__': {TEXT_SPAN_START_FEATURE: start, TEXT_SPAN_END_FEATURE: end}}


def SpanFieldsOld(fields: dict[str, Field] = {}) -> dict[str, Field]:
  """Return the span item from an item."""
  return {
      **fields, '__textspan__':
          Field(
              fields={
                  TEXT_SPAN_START_FEATURE: Field(dtype=DataType.INT32),
                  TEXT_SPAN_END_FEATURE: Field(dtype=DataType.INT32)
              })
  }


def SpanField() -> Field:
  """Return the span item from an item."""
  return Field(
      fields={
          '__textspan__':
              Field(
                  fields={
                      TEXT_SPAN_START_FEATURE: Field(dtype=DataType.INT32),
                      TEXT_SPAN_END_FEATURE: Field(dtype=DataType.INT32)
                  })
      })
