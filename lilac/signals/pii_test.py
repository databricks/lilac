"""Test the PII signal."""


from ..schema import Item
from ..splitters.text_splitter_test_utils import text_to_expected_spans
from .pii import PII_CATEGORIES, SECRETS_KEY, PIISignal


def make_pii_dict(entries: dict[str, list[Item]]) -> dict[str, list[Item]]:
  """Make a PII dictionary with the given kwargs."""
  return {**{cat: [] for cat in list(PII_CATEGORIES.values()) + [SECRETS_KEY]}, **entries}


def test_pii_fields() -> None:
  signal = PIISignal()
  fields = signal.fields().fields
  assert fields is not None
  assert fields.keys() == set(list(PII_CATEGORIES.values()) + [SECRETS_KEY])


def test_pii_compute() -> None:
  signal = PIISignal()

  text = 'This is an email nik@test.com. pii@gmail.com are where emails are read.'
  emails = list(signal.compute([text]))

  expected_spans = text_to_expected_spans(text, ['nik@test.com', 'pii@gmail.com'])

  assert emails == [make_pii_dict({'email_address': expected_spans})]


def test_pii_case_insensitive() -> None:
  signal = PIISignal()

  text = 'These are some emails: NIK@Test.com. pII@gmAIL.COM are where emails are read.'
  emails = list(signal.compute([text]))

  expected_spans = text_to_expected_spans(text, ['NIK@Test.com', 'pII@gmAIL.COM'])

  assert emails == [make_pii_dict({'email_address': expected_spans})]


def test_ip_addresses() -> None:
  signal = PIISignal()

  text = 'These are some ip addresses: 192.158.1.38 and 2001:db8:3333:4444:5555:6666:7777:8888'
  pii = list(signal.compute([text]))
  expected_spans = text_to_expected_spans(
    text, ['192.158.1.38', '2001:db8:3333:4444:5555:6666:7777:8888']
  )
  assert pii == [make_pii_dict({'ip_address': expected_spans})]


def test_secrets() -> None:
  signal = PIISignal()

  text = 'These are some secrets: AKIATESTTESTTESTTEST'
  pii = list(signal.compute([text]))
  expected_spans = text_to_expected_spans(text, ['AKIATESTTESTTESTTEST'])
  assert pii == [make_pii_dict({SECRETS_KEY: expected_spans})]


def test_no_unicode_error() -> None:
  signal = PIISignal()

  text = 'Olof Heden and Denis S. Krotov \u2217'
  expected_spans = text_to_expected_spans(text, ['Olof Heden', 'Denis S. Krotov'])
  pii = list(signal.compute([text]))
  assert pii == [make_pii_dict({})]
