"""Utilities for working with splitters."""

from ...schema import DataType, Field, Item

TEXT_SPAN_FEATURE_NAME = '__textspan__'
TEXT_SPAN_START_FEATURE = 'start'
TEXT_SPAN_END_FEATURE = 'end'

TextSpan = tuple[int, int]


def SpanItem(span: TextSpan, item: Item = {}) -> Item:
  """Return the span item from an item."""
  # Add the span dictionary to the item.
  start, end = span
  return {
      **item, TEXT_SPAN_FEATURE_NAME: {
          TEXT_SPAN_START_FEATURE: start,
          TEXT_SPAN_END_FEATURE: end
      }
  }


def SpanFields(fields: dict[str, Field] = {}) -> dict[str, Field]:
  """Return the span item from an item."""
  return {
      **fields, TEXT_SPAN_FEATURE_NAME:
          Field(
              fields={
                  TEXT_SPAN_START_FEATURE: Field(dtype=DataType.INT32),
                  TEXT_SPAN_END_FEATURE: Field(dtype=DataType.INT32)
              })
  }
