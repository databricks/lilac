"""Compute text statistics for a document."""
import re
from typing import Iterable, Optional

from typing_extensions import override

from ..schema import Field, Item, RichData, SignalInputType, field, lilac_span
from ..signal import TextSignal

EMAILS_KEY = 'emails'
IPS_KEY = 'ip_addresses'
SECRETS_KEY = 'secrets'

# This regex is a fully RFC 5322 regex for email addresses.
# https://uibakery.io/regex-library/email-regex-python
EMAIL_REGEX = re.compile(
  "(?:[a-z0-9!#$%&'*+/=?^_`{|}~-]+(?:\\.[a-z0-9!#$%&'*+/=?^_`{|}~-]+)*|\"(?:[\\x01-\\x08\\x0b\\x0c\\x0e-\\x1f\\x21\\x23-\\x5b\\x5d-\\x7f]|\\\\[\\x01-\\x09\\x0b\\x0c\\x0e-\\x7f])*\")@(?:(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\\.)+[a-z0-9](?:[a-z0-9-]*[a-z0-9])?|\\[(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?|[a-z0-9-]*[a-z0-9]:(?:[\\x01-\\x08\\x0b\\x0c\\x0e-\\x1f\\x21-\\x5a\\x53-\\x7f]|\\\\[\\x01-\\x09\\x0b\\x0c\\x0e-\\x7f])+)\\])",
  re.IGNORECASE)


class PIISignal(TextSignal):
  """Find personally identifiable information (emails, phone numbers, secret keys, etc)."""
  name = 'pii'
  display_name = 'Personal Information (PII)'

  input_type = SignalInputType.TEXT

  @override
  def fields(self) -> Field:
    return field(fields={
      EMAILS_KEY: ['string_span'],
      IPS_KEY: ['string_span'],
      SECRETS_KEY: ['string_span'],
    })

  @override
  def compute(self, data: Iterable[RichData]) -> Iterable[Optional[Item]]:
    try:
      from .pii_ip_address import find_ip_addresses
      from .pii_secrets import find_secrets
    except ImportError:
      raise ImportError('Could not import dependencies for the "PII" signal. '
                        'Please install optional dependencies via `pip install lilac[pii]`.')
    for text in data:
      if not isinstance(text, str):
        yield None
        continue
      emails = [lilac_span(m.start(0), m.end(0)) for m in EMAIL_REGEX.finditer(text)]
      ips = list(find_ip_addresses(text))
      secrets = list(find_secrets(text))
      yield {
        EMAILS_KEY: emails,
        IPS_KEY: ips,
        SECRETS_KEY: secrets,
      }
