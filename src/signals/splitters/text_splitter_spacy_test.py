"""Tests the spacy sentence splitter."""

from .text_splitter_spacy import SentenceSplitterSpacy
from .text_splitter_test_utils import text_to_expected_spans


def test_splitter_spacy() -> None:
  signal = SentenceSplitterSpacy()
  text = 'Hello. This is a test. Final sentence.'

  # Compute over the text.
  split_items = list(signal.compute(data=[text]))

  expected_spans = text_to_expected_spans(text, ['Hello.', 'This is a test.', 'Final sentence.'])

  assert split_items == [expected_spans]


def test_splitter_spacy_float() -> None:
  signal = SentenceSplitterSpacy()
  text = 1.2

  # Compute over the input, make sure it doesn't crash when we pass a non-string value which can
  # happen accidentally in user data.
  split_items = list(signal.compute(data=[text]))  # type: ignore

  assert split_items == [None]
