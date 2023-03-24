"""Test the text splitter utils."""

from .text_splitter import TextSpan
from .text_splitter_test_utils import text_to_expected_spans


def test_text_to_expected_spans() -> None:
  """Tests the sentences_to_expected_spans function."""
  text = 'Hello. Hello. Final sentence.'
  sentences = ['Hello.', 'Hello.', 'Final sentence.']
  assert text_to_expected_spans(text, sentences) == [
      TextSpan(start=0, end=6),
      TextSpan(start=7, end=13),
      TextSpan(start=14, end=29)
  ]
