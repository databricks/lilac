"""Tests the spacy sentence splitter."""

from typing import cast

from .text_splitter_spacy import SentenceSplitterSpacy
from .text_splitter_test_utils import text_to_expected_spans


def test_splitter_spacy() -> None:
  signal = SentenceSplitterSpacy()
  signal.setup()
  text = 'Hello. This is a test. Final sentence.'

  # Compute over the text.
  split_items = list(signal.compute([text]))

  expected_spans = text_to_expected_spans(text, ['Hello.', 'This is a test.', 'Final sentence.'])
  assert split_items == [expected_spans]


def test_spacy_key() -> None:
  signal = SentenceSplitterSpacy()
  assert signal.key() == 'sentences'


def test_spacy_non_en_key() -> None:
  signal = SentenceSplitterSpacy(language='es')
  assert signal.key() == 'sentences(language=es)'


def test_splitter_spacy_float() -> None:
  signal = SentenceSplitterSpacy()
  signal.setup()
  text = 1.2

  # Compute over the input, make sure it doesn't crash when we pass a non-string value which can
  # happen accidentally in user data.
  split_items = list(signal.compute([cast(str, text)]))

  assert split_items == [None]
