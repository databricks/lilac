"""Tests the spacy sentence splitter."""

from typing import cast

from ...schema import Entity
from .text_splitter_spacy import SentenceSplitterSpacy
from .text_splitter_test_utils import text_to_expected_spans


def test_splitter_spacy() -> None:
  signal = SentenceSplitterSpacy()
  text = 'Hello. This is a test. Final sentence.'

  # Compute over the text.
  split_items = list(signal.compute([text]))

  expected_spans = text_to_expected_spans(text, ['Hello.', 'This is a test.', 'Final sentence.'])
  expected_entities = [Entity(span) for span in expected_spans]

  assert split_items == [expected_entities]


def test_splitter_spacy_float() -> None:
  signal = SentenceSplitterSpacy()
  text = 1.2

  # Compute over the input, make sure it doesn't crash when we pass a non-string value which can
  # happen accidentally in user data.
  split_items = list(signal.compute([cast(str, text)]))

  assert split_items == [None]
