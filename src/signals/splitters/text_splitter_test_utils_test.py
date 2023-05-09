"""Test the text splitter utils."""

from ...data.dataset_utils import lilac_span, signal_item
from .text_splitter_test_utils import text_to_expected_spans


def test_text_to_expected_spans() -> None:
  """Tests the sentences_to_expected_spans function."""
  text = 'Hello. Hello. Final sentence.'
  sentences = ['Hello.', 'Hello.', 'Final sentence.']
  assert text_to_expected_spans(text, sentences) == [
    signal_item(lilac_span(0, 6)),
    signal_item(lilac_span(7, 13)),
    signal_item(lilac_span(14, 29))
  ]
