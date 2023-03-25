"""Tests the spacy sentence splitter."""

from .splitter import SpanItem
from .text_splitter_spacy import SENTENCES_FEATURE_NAME, SentenceSplitterSpacy
from .text_splitter_test_utils import text_to_expected_spans


def test_splitter_spacy() -> None:
  signal = SentenceSplitterSpacy()
  text = 'Hello. This is a test. Final sentence.'

  # Compute over the text.
  split_items = list(signal.compute(data=[text]))

  expected_spans = text_to_expected_spans(text, ['Hello.', 'This is a test.', 'Final sentence.'])
  expected_items = [{SENTENCES_FEATURE_NAME: [SpanItem(span=span) for span in expected_spans]}]

  assert split_items == expected_items
