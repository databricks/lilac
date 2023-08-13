"""Test the PII signal."""

from ..schema import field
from ..splitters.text_splitter_test_utils import text_to_expected_spans
from .pii import EMAILS_KEY, IPS_KEY, SECRETS_KEY, PIISignal


def test_pii_fields() -> None:
  signal = PIISignal()
  assert signal.fields() == field(fields={
    EMAILS_KEY: ['string_span'],
    IPS_KEY: ['string_span'],
    SECRETS_KEY: ['string_span']
  })


def test_pii_compute() -> None:
  signal = PIISignal()

  text = 'This is an email nik@test.com. pii@gmail.com are where emails are read.'
  emails = list(signal.compute([text]))

  expected_spans = text_to_expected_spans(text, ['nik@test.com', 'pii@gmail.com'])

  assert emails == [{EMAILS_KEY: expected_spans, IPS_KEY: [], SECRETS_KEY: []}]


def test_pii_case_insensitive() -> None:
  signal = PIISignal()

  text = 'These are some emails: NIK@Test.com. pII@gmAIL.COM are where emails are read.'
  emails = list(signal.compute([text]))

  expected_spans = text_to_expected_spans(text, ['NIK@Test.com', 'pII@gmAIL.COM'])

  assert emails == [{EMAILS_KEY: expected_spans, IPS_KEY: [], SECRETS_KEY: []}]


def test_ip_addresses() -> None:
  signal = PIISignal()

  text = 'These are some ip addresses: 192.158.1.38 and 2001:db8:3333:4444:5555:6666:7777:8888'
  pii = list(signal.compute([text]))
  expected_spans = text_to_expected_spans(
    text, ['192.158.1.38', '2001:db8:3333:4444:5555:6666:7777:8888'])
  assert pii == [{EMAILS_KEY: [], IPS_KEY: expected_spans, SECRETS_KEY: []}]


def test_secrets() -> None:
  signal = PIISignal()

  text = 'These are some secrets: AKIATESTTESTTESTTEST'
  pii = list(signal.compute([text]))
  expected_spans = text_to_expected_spans(text, ['AKIATESTTESTTESTTEST'])
  assert pii == [{EMAILS_KEY: [], IPS_KEY: [], SECRETS_KEY: expected_spans}]
