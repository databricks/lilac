"""Test the PII signal."""

from ..schema import field
from .pii import EMAILS_KEY, NUM_EMAILS_KEY, PIISignal
from .splitters.text_splitter_test_utils import text_to_expected_spans


def test_pii_fields() -> None:
  signal = PIISignal()
  assert signal.fields() == field(fields={EMAILS_KEY: ['string_span'], NUM_EMAILS_KEY: 'int32'})


def test_pii_compute() -> None:
  signal = PIISignal()

  text = 'This is an email nik@test.com. pii@gmail.com are where emails are read.'
  emails = list(signal.compute([text]))

  expected_spans = text_to_expected_spans(text, ['nik@test.com', 'pii@gmail.com'])

  assert emails == [{EMAILS_KEY: expected_spans, NUM_EMAILS_KEY: 2}]


def test_pii_case_insensitive() -> None:
  signal = PIISignal()

  text = 'These are some emails: NIK@Test.com. pII@gmAIL.COM are where emails are read.'
  emails = list(signal.compute([text]))

  expected_spans = text_to_expected_spans(text, ['NIK@Test.com', 'pII@gmAIL.COM'])

  assert emails == [{EMAILS_KEY: expected_spans, NUM_EMAILS_KEY: 2}]
