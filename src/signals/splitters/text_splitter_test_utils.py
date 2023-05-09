"""Utilities for testing text splitters."""

from ...data.dataset_utils import lilac_span
from ...schema import Item


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
