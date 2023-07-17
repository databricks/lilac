"""Compute text statistics for a document."""
import ipaddress
import re
from typing import Iterable, Iterator, Optional

import regex
from typing_extensions import override

from ..data.dataset_utils import lilac_span
from ..schema import Field, Item, RichData, SignalInputType, field
from .signal import TextSignal

EMAILS_KEY = 'emails'
IPS_KEY = 'ip_addresses'
NUM_EMAILS_KEY = 'num_emails'

# This regex is a fully RFC 5322 regex for email addresses.
# https://uibakery.io/regex-library/email-regex-python
EMAIL_REGEX = re.compile(
  "(?:[a-z0-9!#$%&'*+/=?^_`{|}~-]+(?:\\.[a-z0-9!#$%&'*+/=?^_`{|}~-]+)*|\"(?:[\\x01-\\x08\\x0b\\x0c\\x0e-\\x1f\\x21\\x23-\\x5b\\x5d-\\x7f]|\\\\[\\x01-\\x09\\x0b\\x0c\\x0e-\\x7f])*\")@(?:(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\\.)+[a-z0-9](?:[a-z0-9-]*[a-z0-9])?|\\[(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?|[a-z0-9-]*[a-z0-9]:(?:[\\x01-\\x08\\x0b\\x0c\\x0e-\\x1f\\x21-\\x5a\\x53-\\x7f]|\\\\[\\x01-\\x09\\x0b\\x0c\\x0e-\\x7f])+)\\])",
  re.IGNORECASE)


class PIISignal(TextSignal):
  """Find personally identifiable information (emails, phone numbers, etc)."""
  name = 'pii'
  display_name = 'Personal Information (PII)'

  input_type = SignalInputType.TEXT
  compute_type = SignalInputType.TEXT

  @override
  def fields(self) -> Field:
    return field(fields={EMAILS_KEY: ['string_span'], NUM_EMAILS_KEY: 'int32'})

  @override
  def compute(self, data: Iterable[RichData]) -> Iterable[Optional[Item]]:
    for text in data:
      if not isinstance(text, str):
        yield None
        continue
      emails = [lilac_span(m.start(0), m.end(0)) for m in EMAIL_REGEX.finditer(text)]
      ips = list(_get_ips(text))
      yield {EMAILS_KEY: emails, NUM_EMAILS_KEY: len(emails), IPS_KEY: ips}


# Code below is forked from
# https://github.com/bigcode-project/pii-lib/blob/main/utils/emails_ip_addresses_detection.py
# under the Apache 2.0 License.

ipv4_pattern = r'(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)(?:\.(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)){3}'  # noqa: E501
ipv6_pattern = r'(?:[0-9a-fA-F]{1,4}:){7,7}[0-9a-fA-F]{1,4}|(?:[0-9a-fA-F]{1,4}:){1,7}:|(?:[0-9a-fA-F]{1,4}:){1,6}:[0-9a-fA-F]{1,4}|(?:[0-9a-fA-F]{1,4}:){1,5}(?::[0-9a-fA-F]{1,4}){1,2}|(?:[0-9a-fA-F]{1,4}:){1,4}(?::[0-9a-fA-F]{1,4}){1,3}|(?:[0-9a-fA-F]{1,4}:){1,3}(?::[0-9a-fA-F]{1,4}){1,4}|(?:[0-9a-fA-F]{1,4}:){1,2}(?::[0-9a-fA-F]{1,4}){1,5}|[0-9a-fA-F]{1,4}:(?:(?::[0-9a-fA-F]{1,4}){1,6})|:(?:(?::[0-9a-fA-F]{1,4}){1,7}|:)|fe80:(?::[0-9a-fA-F]{0,4}){0,4}%[0-9a-zA-Z]{1,}|::(?:ffff(?::0{1,4}){0,1}:){0,1}(?:(?:25[0-5]|(?:2[0-4]|1{0,1}[0-9]){0,1}[0-9])\.){3,3}(?:25[0-5]|(?:2[0-4]|1{0,1}[0-9]){0,1}[0-9])|(?:[0-9a-fA-F]{1,4}:){1,4}:(?:(?:25[0-5]|(?:2[0-4]|1{0,1}[0-9]){0,1}[0-9])\.){3,3}(25[0-5]|(?:2[0-4]|1{0,1}[0-9]){0,1}[0-9])'  # noqa: E501
ip_pattern = regex.compile(
  (r'(?:^|[\b\s@?,!;:\'\")(.\p{Han}])(' + r'|'.join([ipv4_pattern, ipv6_pattern]) +
   ')(?:$|[\\s@,?!;:\'\"(.\\p{Han}])'))

year_patterns = [
  regex.compile(
    r"(?:^|[\b\s@?,!;:\'\")(.\p{Han}])([1-2][0-9]{3}[\p{Pd}/][1-2][0-9]{3})(?:$|[\s@,?!;:\'\"(.\p{Han}])"
  ),  # yyyy-yyyy or yyyy/yyyy
  regex.compile(
    r"(?:^|[\b\s@?,!;:\'\")(.\p{Han}])([1-2][0-9]{3}[\p{Pd}/.][0-3][0-9][\p{Pd}/.][0-3][0-9])(?:$|[\s@,?!;:\'\"(.\p{Han}])"
  ),  # yyyy-mm-dd or yyyy-dd-mm or yyyy/mm/dd or yyyy/dd/mm or yyyy.mm.dd or yyyy.dd.mm
  regex.compile(
    r"(?:^|[\b\s@?,!;:\'\")(.\p{Han}])([0-3][0-9][\p{Pd}/.][0-3][0-9][\p{Pd}/.](?:[0-9]{2}|[1-2][0-9]{3}))(?:$|[\s@,?!;:\'\"(.\p{Han}])"
  ),  # mm-dd-yyyy or dd-mm-yyyy or mm/dd/yyyy or dd/mm/yyyy or mm.dd.yyyy or dd.mm.yyyy
  regex.compile(
    r"(?:^|[\b\s@?,!;:\'\")(.\p{Han}])([0-3][0-9][\p{Pd}/](?:[0-9]{2}|[1-2][0-9]{3}))(?:$|[\s@,?!;:\'\"(.\p{Han}])"
  ),  # mm-yyyy or mm/yyyy or the same but with yy
  regex.compile(
    r"(?:^|[\b\s@?,!;:\'\")(.\p{Han}])([1-2][0-9]{3}-[0-3][0-9])(?:$|[\s@,?!;:\'\"(.\p{Han}])"
  ),  # yyyy-mm or yyyy/mm
]


def _ip_has_digit(matched_str: str) -> bool:
  """Checks to make sure the PII span is not just ::."""
  return any(map(str.isdigit, matched_str))


def _matches_date_pattern(matched_str: str) -> bool:
  # Screen out date false positives.
  for year_regex in year_patterns:
    if year_regex.match(matched_str):
      return True
  return False


def filter_versions(matched_str: str, context: str) -> bool:
  """Filter x.x.x.x and the words dns/server don't appear in the context."""
  # count occurrence of dots.
  dot_count = matched_str.count('.')
  exclude = (dot_count == 3 and len(matched_str) == 7)
  if exclude:
    if 'dns' in context.lower() or 'server' in context.lower():
      return False
  return exclude


def not_ip_address(matched_str: str) -> bool:
  """Make sure the string has a valid IP address format e.g: 33.01.33.33 is not a valid."""
  try:
    ipaddress.ip_address(matched_str)
    return False
  except ValueError:
    return True


def _get_ips(text: str) -> Iterator[Item]:
  for match in ip_pattern.finditer(text):
    if not match.groups():
      continue
    value = match.group(1)
    start, end = match.span(1)
    # Filter out false positive IPs
    if not _ip_has_digit(value):
      continue
    if _matches_date_pattern(value):
      continue
    if filter_versions(value, text[start - 100:end + 100]) or not_ip_address(value):
      continue
    yield lilac_span(start, end)
