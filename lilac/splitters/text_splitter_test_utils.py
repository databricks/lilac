"""Utilities for testing text splitters."""

from typing import Optional, Union

from ..schema import TEXT_SPAN_END_FEATURE, TEXT_SPAN_START_FEATURE, VALUE_KEY, Item, lilac_span


def spans_to_text(text: str, spans: Optional[list[Item]]) -> list[str]:
  """Convert text and a list of spans to a list of strings."""
  if not spans:
    return []
  return [
    text[span[VALUE_KEY][TEXT_SPAN_START_FEATURE]:span[VALUE_KEY][TEXT_SPAN_END_FEATURE]]
    for span in spans
  ]


def text_to_expected_spans(text: str, splits: Union[list[str], list[tuple[str,
                                                                          Item]]]) -> list[Item]:
  """Convert text and a list of splits to a list of expected spans."""
  start_offset = 0
  expected_spans: list[Item] = []
  for split in splits:
    item: Item
    if isinstance(split, str):
      split, item = split, {}
    elif isinstance(split, tuple):
      split, item = split
    else:
      raise ValueError('Split should be a string or a tuple of (string, item dict).')
    start = text.find(split, start_offset)
    end = start + len(split)
    expected_spans.append(lilac_span(start=start, end=end, metadata=item))
    start_offset = end

  return expected_spans
