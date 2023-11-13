"""Wrap Presidio library for detecting PII in text."""
import functools

from presidio_analyzer import AnalyzerEngine
from presidio_analyzer.nlp_engine import SpacyNlpEngine
from presidio_analyzer.nlp_engine.ner_model_configuration import NerModelConfiguration

from ..schema import Item, lilac_span

## Circular import; we would like to lazy import this module as it uses optional dependencies.
from .pii import PII_CATEGORIES

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

SPACY_MODEL = 'en_core_web_sm'  # Small model, ~12MB. See https://spacy.io/models/en

# Presidio spits out some false positives; set a confidence threshold for certain categories.
CATEGORY_THRESHOLDS = {
  'PHONE_NUMBER': 0.5,
}


@functools.lru_cache()
def _get_analyzer() -> AnalyzerEngine:
  spacy_engine = SpacyNlpEngine(
    models=[{'lang_code': 'en', 'model_name': SPACY_MODEL}],
    ner_model_configuration=NerModelConfiguration(
      labels_to_ignore=IGNORED_SPACY_ENTITIES,
    ),
  )
  return AnalyzerEngine(nlp_engine=spacy_engine)


def find_pii(text: str) -> dict[str, list[Item]]:
  """Find personally identifiable information (emails, phone numbers, etc)."""
  results = _get_analyzer().analyze(text, entities=list(PII_CATEGORIES), language='en')
  pii_dict: dict[str, list[Item]] = {cat: [] for cat in PII_CATEGORIES.values()}
  for result in results:
    if CATEGORY_THRESHOLDS.get(result.entity_type, 0) > result.score:
      continue
    pii_dict[PII_CATEGORIES[result.entity_type]].append(lilac_span(result.start, result.end))
  return pii_dict
