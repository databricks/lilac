"""Utilities for testing text splitters."""

from typing import Optional

from ...data.dataset_utils import lilac_span
from ...schema import TEXT_SPAN_END_FEATURE, TEXT_SPAN_START_FEATURE, VALUE_KEY, Item


def spans_to_text(text: str, spans: Optional[list[Item]]) -> list[str]:
  """Convert text and a list of spans to a list of strings."""
  if not spans:
    return []
  return [
    text[span[VALUE_KEY][TEXT_SPAN_START_FEATURE]:span[VALUE_KEY][TEXT_SPAN_END_FEATURE]]
    for span in spans
  ]


def text_to_expected_spans(text: str, splits: list[str]) -> list[Item]:
  """Convert text and a list of splits to a list of expected spans."""
  start_offset = 0
  expected_spans: list[Item] = []
  for split in splits:
    start = text.find(split, start_offset)
    end = start + len(split)
    expected_spans.append(lilac_span(start=start, end=end))
    start_offset = end

  return expected_spans
