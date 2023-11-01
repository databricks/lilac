"""Utilities for testing text splitters."""

from typing import Optional, Union

from ..schema import SPAN_KEY, TEXT_SPAN_END_FEATURE, TEXT_SPAN_START_FEATURE, Item, lilac_span
from .chunk_splitter import TextChunk


def spans_to_text(text: str, spans: Optional[list[Item]]) -> list[str]:
  """Convert text and a list of spans to a list of strings."""
  if not spans:
    return []
  return [
    text[span[SPAN_KEY][TEXT_SPAN_START_FEATURE] : span[SPAN_KEY][TEXT_SPAN_END_FEATURE]]
    for span in spans
  ]


def text_to_expected_spans(
  text: str, splits: Union[list[str], list[tuple[str, Item]]], allowable_overlap: int = 0
) -> list[Item]:
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
    start_offset = end - allowable_overlap

  return expected_spans


def text_to_textchunk(text: str, splits: list[str], allowable_overlap: int = 0) -> list[TextChunk]:
  """Convert text and a list of splits to a list of TextChunks."""
  spans = text_to_expected_spans(text, splits, allowable_overlap=allowable_overlap)
  expected_textchunks = []
  for span in spans:
    start, end = span[SPAN_KEY][TEXT_SPAN_START_FEATURE], span[SPAN_KEY][TEXT_SPAN_END_FEATURE]
    expected_textchunks.append((text[start:end], (start, end)))
  return expected_textchunks


def clean_textchunks(chunks: list[TextChunk]) -> list[TextChunk]:
  """Strip whitespace from TextChunks."""

  def clean_chunk(chunk: TextChunk) -> TextChunk:
    text, (start, _) = chunk
    stripped_text = text.strip()
    new_start = text.find(stripped_text) + start
    new_end = new_start + len(stripped_text)
    return stripped_text, (new_start, new_end)

  return [clean_chunk(chunk) for chunk in chunks]
