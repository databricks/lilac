"""Tests the spacy chunk splitter."""

from .spacy_splitter import clustering_spacy_chunker, simple_spacy_chunker
from .text_splitter_test_utils import clean_textchunks, text_to_textchunk


def test_short_snippets_filtered() -> None:
  text = '1. Hello. 2. World.'
  expected_spans = text_to_textchunk(text, ['Hello.', 'World.'])

  split_items = simple_spacy_chunker(text)
  assert split_items == expected_spans


def test_colon_considered_as_splitter() -> None:
  text = 'Teacher: Tell me the answer. Student: I have no idea.'
  expected_spans = text_to_textchunk(
    text, ['Teacher:', 'Tell me the answer.', 'Student:', 'I have no idea.']
  )
  split_items = simple_spacy_chunker(text)
  assert split_items == expected_spans


def test_long_spans_default_split() -> None:
  text = 'Blah blah blah.'
  expected_spans = text_to_textchunk(text, ['Blah bl', 'ah blah.'])

  split_items = clustering_spacy_chunker(text, max_len=8)
  assert split_items == expected_spans


def test_long_spans_preferred_splits() -> None:
  text = 'Blah. blah. bla. bl.'
  expected_spans = text_to_textchunk(text, ['Blah.', 'blah.', 'bla.', 'bl.'])
  # Even though target_num_groups = 1, the max len constraint causes breaking.
  split_items = clustering_spacy_chunker(text, target_num_groups=1, max_len=6, filter_short=1)
  assert clean_textchunks(split_items) == expected_spans


def test_similar_spans_grouped() -> None:
  text = 'Blah1. Blah2. Blah2.'
  expected_spans = text_to_textchunk(text, ['Blah1.', 'Blah2. Blah2.'])
  split_items = clustering_spacy_chunker(text, target_num_groups=2)
  assert clean_textchunks(split_items) == expected_spans


def test_fewer_than_desired_groups() -> None:
  text = 'blah blah blah'
  expected_spans = text_to_textchunk(text, ['blah blah blah'])
  split_items = clustering_spacy_chunker(text, target_num_groups=4)
  assert clean_textchunks(split_items) == expected_spans


def test_no_chunks_emitted() -> None:
  text = ''
  split_items = clustering_spacy_chunker(text, target_num_groups=4)
  assert split_items == []
