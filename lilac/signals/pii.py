"""Compute text statistics for a document."""
from typing import ClassVar, Iterable, Optional

from typing_extensions import override

from ..schema import Field, Item, RichData, SignalInputType, field
from ..signal import TextSignal

SECRETS_KEY = 'secrets'
# Selected categories. For all categories, see:
# https://microsoft.github.io/presidio/supported_entities/

PII_CATEGORIES = [
  'CREDIT_CARD',
  'CRYPTO',
  'EMAIL_ADDRESS',
  'IBAN_CODE',
  'IP_ADDRESS',
  'PHONE_NUMBER',
  'MEDICAL_LICENSE',
]


class PIISignal(TextSignal):
  """Find personally identifiable information (emails, phone numbers, secret keys, etc)."""

  name: ClassVar[str] = 'pii'
  display_name: ClassVar[str] = 'Personal Information (PII)'

  input_type: ClassVar[SignalInputType] = SignalInputType.TEXT

  @override
  def fields(self) -> Field:
    return field(
      fields={**{cat: ['string_span'] for cat in PII_CATEGORIES}, SECRETS_KEY: ['string_span']}
    )

  @override
  def compute(self, data: Iterable[RichData]) -> Iterable[Optional[Item]]:
    try:
      from .pii_presidio import find_pii
      from .pii_secrets import find_secrets
    except ImportError:
      raise ImportError(
        'Could not import dependencies for the "PII" signal. '
        'Please install optional dependencies via `pip install lilac[pii]`.'
      )
    for text in data:
      if not isinstance(text, str):
        yield None
        continue

      secrets = list(find_secrets(text))
      pii_dict = find_pii(text)
      yield {**pii_dict, SECRETS_KEY: secrets}
