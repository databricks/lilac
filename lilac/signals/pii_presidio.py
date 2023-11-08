import presidio_analyzer

from ..schema import Item, lilac_span

# Selected categories. For all categories, see:
# https://microsoft.github.io/presidio/supported_entities/
PII_CATEGORIES = [
  'CREDIT_CARD',
  'CRYPTO',
  'EMAIL_ADDRESS',
  'IBAN_CODE',
  'IP_ADDRESS',
  'PERSON',
  'PHONE_NUMBER',
  'MEDICAL_LICENSE',
]

ANALYZER = presidio_analyzer.AnalyzerEngine()


def find_pii(text: str) -> dict[str, list[Item]]:
  """Find personally identifiable information (emails, phone numbers, etc)."""
  results = ANALYZER.analyze(text, entities=PII_CATEGORIES, language='en')
  pii_dict = {cat: [] for cat in PII_CATEGORIES}
  for result in results:
    pii_dict[result.entity_type].append(lilac_span(result.start, result.end))
  return pii_dict
