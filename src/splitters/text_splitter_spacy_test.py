"""Tests the spacy sentence splitter."""

from .text_splitter_spacy import SentenceSplitterSpacy
from .text_splitter_test_utils import text_to_expected_spans


def test_split_sentences() -> None:
  """Tests the split function."""
  splitter = SentenceSplitterSpacy()

  text = 'Hello. This is a test. Final sentence.'
  text_spans = splitter.split(text)

  expected_sentences = ['Hello.', 'This is a test.', 'Final sentence.']
  assert text_spans == text_to_expected_spans(text, expected_sentences)
