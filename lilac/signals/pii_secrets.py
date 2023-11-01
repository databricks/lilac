"""Find secret keys in text.

# Code forked from
# https://github.com/bigcode-project/pii-lib/blob/main/utils/keys_detection.py
# under the Apache 2.0 License.
"""
import os
import tempfile
from typing import Iterator

from detect_secrets import SecretsCollection
from detect_secrets.settings import transient_settings

from ..schema import Item, lilac_span

# Secrets detection with detect-secrets tool

filters = [
  # some filters from
  # https://github.com/Yelp/detect-secrets/blob/master/docs/filters.md#built-in-filters
  # were removed based on their targets
  {'path': 'detect_secrets.filters.heuristic.is_potential_uuid'},
  {'path': 'detect_secrets.filters.heuristic.is_likely_id_string'},
  {'path': 'detect_secrets.filters.heuristic.is_templated_secret'},
  {'path': 'detect_secrets.filters.heuristic.is_sequential_string'},
]
plugins = [
  {'name': 'ArtifactoryDetector'},
  {'name': 'AWSKeyDetector'},
  {'name': 'AzureStorageKeyDetector'},
  {'name': 'CloudantDetector'},
  {'name': 'DiscordBotTokenDetector'},
  {'name': 'GitHubTokenDetector'},
  {'name': 'IbmCloudIamDetector'},
  {'name': 'IbmCosHmacDetector'},
  {'name': 'JwtTokenDetector'},
  {'name': 'MailchimpDetector'},
  {'name': 'NpmDetector'},
  {'name': 'SendGridDetector'},
  {'name': 'SlackDetector'},
  {'name': 'SoftlayerDetector'},
  {'name': 'StripeDetector'},
  {'name': 'TwilioKeyDetector'},
  # remove 3 plugins for keyword
  # {'name': 'BasicAuthDetector'},
  # {'name': 'KeywordDetector'},
  # {'name': 'PrivateKeyDetector'},
]


def _is_hash(content: str, value: str) -> bool:
  """Second check if the value is a hash (after gibberish detector)."""
  try:
    index = content.index(value)
  except ValueError:
    return False
  lines = content[:index].splitlines()
  if not lines:
    return False
  target_line = lines[-1]
  if len(value) in [32, 40, 64]:
    # if 'sha' or 'md5' are in content:
    keywords = ['sha', 'md5', 'hash', 'byte']
    if any(x in target_line.lower() for x in keywords):
      return True
  return False


def _file_has_hashes(content: str, coeff: float = 0.02) -> bool:
  """Checks if the file contains literals 'hash' or 'sha' for more than 2% nb_of_lines."""
  lines = content.splitlines()
  count_sha = 0
  count_hash = 0
  nlines = content.count('\n')
  threshold = int(coeff * nlines)
  for line in lines:
    count_sha += line.lower().count('sha')
    count_hash += line.lower().count('hash')
    if count_sha > threshold or count_hash > threshold:
      return True
  return False


def _get_indexes(text: str, value: str) -> list[tuple[int, int]]:
  string = text
  indexes: list[int] = []
  new_start = 0
  while True:
    try:
      start = string.index(value)
      indexes.append(new_start + start)
      new_start = new_start + start + len(value)
      string = text[new_start:]
    except ValueError:
      break
  return [(x, x + len(value)) for x in indexes]


def find_secrets(content: str, suffix: str = '.txt') -> Iterator[Item]:
  """Detect secret keys in content using detect-secrets tool."""
  fp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False, mode='w', encoding='utf-8')
  fp.write(content)
  fp.close()
  secrets = SecretsCollection()
  with transient_settings({'plugins_used': plugins, 'filters_used': filters}):
    secrets.scan_file(fp.name)
  os.unlink(fp.name)
  secrets_set = list(secrets.data.values())
  if not secrets_set:
    return
  for secret in secrets_set[0]:
    if not secret.secret_value:
      continue
    if _is_hash(content, secret.secret_value) or _file_has_hashes(content):
      continue
    indexes = _get_indexes(content, secret.secret_value)
    for start, end in indexes:
      yield lilac_span(start, end)
