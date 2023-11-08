"""Wrap Presidio library for detecting PII in text."""
from presidio_analyzer import AnalyzerEngine
from presidio_analyzer.nlp_engine import SpacyNlpEngine
from presidio_analyzer.nlp_engine.ner_model_configuration import NerModelConfiguration

from ..schema import Item, lilac_span

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


# When SpaCy detects certain entities, but Presidio doesn't know what to do with them, it generates
# logspam. Explicitly ignore these entities to suppress the logspam.
IGNORED_SPACY_ENTITIES = [
  'CARDINAL',
  'EVENT',
  'FAC',
  'LANGUAGE',
  'LAW',
  'MONEY',
  'ORDINAL',
  'PERCENT',
  'PRODUCT',
  'QUANTITY',
  'WORK_OF_ART',
]

SPACY_ENGINE = SpacyNlpEngine(
  models=[{'lang_code': 'en', 'model_name': 'en_core_web_sm'}],
  ner_model_configuration=NerModelConfiguration(
    labels_to_ignore=IGNORED_SPACY_ENTITIES,
  ),
)
ANALYZER = AnalyzerEngine(nlp_engine=SPACY_ENGINE)


def find_pii(text: str) -> dict[str, list[Item]]:
  """Find personally identifiable information (emails, phone numbers, etc)."""
  results = ANALYZER.analyze(text, entities=PII_CATEGORIES, language='en')
  pii_dict: dict[str, list[Item]] = {cat: [] for cat in PII_CATEGORIES}
  for result in results:
    pii_dict[result.entity_type].append(lilac_span(result.start, result.end))
  return pii_dict
