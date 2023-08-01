"""Find ip addresses in text.

# Code forked from
# https://github.com/bigcode-project/pii-lib/blob/main/utils/emails_ip_addresses_detection.py
# under the Apache 2.0 License.
"""
import ipaddress
from typing import Iterator

import regex

from ..schema import Item, lilac_span

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


def _filter_versions(matched_str: str, context: str) -> bool:
  """Filter x.x.x.x and the words dns/server don't appear in the context."""
  # count occurrence of dots.
  dot_count = matched_str.count('.')
  exclude = (dot_count == 3 and len(matched_str) == 7)
  if exclude:
    if 'dns' in context.lower() or 'server' in context.lower():
      return False
  return exclude


def _not_ip_address(matched_str: str) -> bool:
  """Make sure the string has a valid IP address format e.g: 33.01.33.33 is not a valid."""
  try:
    ipaddress.ip_address(matched_str)
    return False
  except ValueError:
    return True


def find_ip_addresses(text: str) -> Iterator[Item]:
  """Find IP addresses in the text."""
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
    if _filter_versions(value, text[start - 100:end + 100]) or _not_ip_address(value):
      continue
    yield lilac_span(start, end)
