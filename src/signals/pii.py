"""Compute text statistics for a document."""
import re
from typing import Iterable, Optional

from typing_extensions import override

from ..data.dataset_utils import lilac_span, signal_item
from ..schema import Field, Item, RichData, SignalInputType, field
from .signal import Signal

EMAILS_KEY = 'emails'
NUM_EMAILS_KEY = 'num_emails'

# This regex is a fully RFC 5322 regex for email addresses.
# https://uibakery.io/regex-library/email-regex-python
EMAIL_REGEX = (
  "(?:[a-z0-9!#$%&'*+/=?^_`{|}~-]+(?:\\.[a-z0-9!#$%&'*+/=?^_`{|}~-]+)*|\"(?:[\\x01-\\x08\\x0b\\x0c\\x0e-\\x1f\\x21\\x23-\\x5b\\x5d-\\x7f]|\\\\[\\x01-\\x09\\x0b\\x0c\\x0e-\\x7f])*\")@(?:(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\\.)+[a-z0-9](?:[a-z0-9-]*[a-z0-9])?|\\[(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?|[a-z0-9-]*[a-z0-9]:(?:[\\x01-\\x08\\x0b\\x0c\\x0e-\\x1f\\x21-\\x5a\\x53-\\x7f]|\\\\[\\x01-\\x09\\x0b\\x0c\\x0e-\\x7f])+)\\])"
)


# NOTE: We don't extend TextSignal so we avoid giving the user the option to compute PII over
# splits as this doesn't add any value and can be confusing.
class PIISignal(Signal):
  """Find personally identifiable information (emails, phone numbers, etc)."""
  name = 'pii'
  display_name = 'Personal Information (PII)'

  input_type = SignalInputType.TEXT
  compute_type = SignalInputType.TEXT

  @override
  def fields(self) -> Field:
    return field({EMAILS_KEY: ['string_span'], NUM_EMAILS_KEY: 'int32'})

  @override
  def compute(self, data: Iterable[RichData]) -> Iterable[Optional[Item]]:
    for text in data:
      if not isinstance(text, str):
        yield None
        continue
      emails = [
        signal_item(lilac_span(m.start(0), m.end(0))) for m in re.finditer(EMAIL_REGEX, text)
      ]
      yield {EMAILS_KEY: emails, NUM_EMAILS_KEY: len(emails)}
