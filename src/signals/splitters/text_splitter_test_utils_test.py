"""Test the text splitter utils."""

from ...schema import TextEntity
from .text_splitter_test_utils import text_to_expected_spans


def test_text_to_expected_spans() -> None:
  """Tests the sentences_to_expected_spans function."""
  text = 'Hello. Hello. Final sentence.'
  sentences = ['Hello.', 'Hello.', 'Final sentence.']
  assert text_to_expected_spans(
    text, sentences) == [TextEntity(0, 6), TextEntity(7, 13),
                         TextEntity(14, 29)]
