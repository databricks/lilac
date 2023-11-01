"""Tests the chunk splitter."""

from .chunk_splitter import split_text
from .text_splitter_test_utils import text_to_textchunk


def test_paragraphs_no_overlap() -> None:
  text = 'Hello.\n\nThis will get split.\n\nThe sentence\n\nA.\n\nB.\n\nC.'
  split_items = split_text(text, chunk_size=12, chunk_overlap=0)

  # "This will get split" should split in 2 chunks, and "A.\n\nB.\n\nC." should be 1 chunk.
  expected_spans = text_to_textchunk(
    text, ['Hello.', 'This will', 'get split.', 'The sentence', 'A.\n\nB.\n\nC.']
  )
  assert split_items == expected_spans


def test_single_world_is_too_long_no_overlap() -> None:
  text = 'ThisIsASingleWordThatIsTooLong'
  split_items = split_text(text, chunk_size=6, chunk_overlap=0)

  expected_spans = text_to_textchunk(text, ['ThisIs', 'ASingl', 'eWordT', 'hatIsT', 'ooLong'])
  assert split_items == expected_spans


def test_newlines_with_overlap() -> None:
  text = 'Hello.\n\nWorld.\n\nThis will get split.'
  split_items = split_text(text, chunk_size=12, chunk_overlap=5)

  expected_chunks = text_to_textchunk(
    text, ['Hello.', 'World.', 'This will', 'will get', 'get split.'], allowable_overlap=5
  )
  assert split_items == expected_chunks
