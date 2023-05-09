"""Test the PII signal."""

from ..schema import field
from .pii import EMAILS_FEATURE_NAME, PIISignal
from .splitters.text_splitter_test_utils import text_to_expected_spans


def test_pii_fields() -> None:
  signal = PIISignal()
  assert signal.fields() == field({EMAILS_FEATURE_NAME: ['string_span']})


def test_pii_compute() -> None:
  signal = PIISignal()

  text = 'This is an email nik@test.com. pii@gmail.com are where emails are read.'
  emails = list(signal.compute([text]))

  expected_spans = text_to_expected_spans(text, ['nik@test.com', 'pii@gmail.com'])

  assert emails == [{EMAILS_FEATURE_NAME: expected_spans}]
