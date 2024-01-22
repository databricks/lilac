"""Compute text statistics for a document."""
from typing import ClassVar, Iterator, Optional

import modal
from typing_extensions import override

from ..batch_utils import compress_docs
from ..schema import Field, Item, RichData, SignalInputType, field
from ..signal import TextSignal
from ..tasks import TaskExecutionType
from ..utils import DebugTimer, chunks

SECRETS_KEY = 'secrets'
# Selected categories. For all categories, see:
# https://microsoft.github.io/presidio/supported_entities/

# Map from Presidio category to UI-visible category name.
PII_CATEGORIES = {
  'CREDIT_CARD': 'credit_card',
  'CRYPTO': 'crypto_address',
  'EMAIL_ADDRESS': 'email_address',
  'IBAN_CODE': 'bank_number',
  'IP_ADDRESS': 'ip_address',
  'PHONE_NUMBER': 'phone_number',
}
PII_LOCAL_BATCH_SIZE = 128
PII_REMOTE_BATCH_SIZE = 512


class PIISignal(TextSignal):
  """Find personally identifiable information (emails, phone numbers, secret keys, etc)."""

  name: ClassVar[str] = 'pii'
  display_name: ClassVar[str] = 'Personal Information (PII)'

  input_type: ClassVar[SignalInputType] = SignalInputType.TEXT

  local_batch_size: ClassVar[Optional[int]] = PII_LOCAL_BATCH_SIZE
  local_parallelism: ClassVar[int] = -1
  local_strategy: ClassVar[TaskExecutionType] = 'processes'
  supports_garden: ClassVar[bool] = True

  @override
  def fields(self) -> Field:
    return field(
      fields={
        **{cat: ['string_span'] for cat in PII_CATEGORIES.values()},
        SECRETS_KEY: ['string_span'],
      }
    )

  @override
  def compute(self, data: list[RichData]) -> list[Optional[Item]]:
    try:
      from .pii_presidio import find_pii
      from .pii_secrets import find_secrets
    except ImportError:
      raise ImportError(
        'Could not import dependencies for the "PII" signal. '
        'Please install optional dependencies via `pip install lilac[pii]`.'
      )
    res: list[Optional[Item]] = []
    for text in data:
      if not isinstance(text, str):
        res.append(None)
        continue

      secrets = list(find_secrets(text))
      pii_dict = find_pii(text)
      res.append({**pii_dict, SECRETS_KEY: secrets})
    return res

  @override
  def compute_garden(self, docs: Iterator[str]) -> Iterator[Item]:
    pii = modal.Function.lookup('pii', 'PII.detect')
    with DebugTimer('Computing PII on Lilac Garden'):
      batches = chunks(docs, PII_REMOTE_BATCH_SIZE)
      requests = ({'gzipped_docs': compress_docs(b)} for b in batches)
      for response in pii.map(requests, order_outputs=True):
        for item in response['result']:
          yield item
