"""Compute text statistics for a document."""
import re
from typing import Iterable, Optional

import spacy
from pydantic import Field as PydanticField
from typing_extensions import override

from ..data.dataset_utils import lilac_span
from ..schema import Field, Item, RichData, SignalInputType, field
from .signal import TextSignal

EMAILS_KEY = 'emails'
NUM_EMAILS_KEY = 'num_emails'

# This regex is a fully RFC 5322 regex for email addresses.
# https://uibakery.io/regex-library/email-regex-python
EMAIL_REGEX = re.compile(
  "(?:[a-z0-9!#$%&'*+/=?^_`{|}~-]+(?:\\.[a-z0-9!#$%&'*+/=?^_`{|}~-]+)*|\"(?:[\\x01-\\x08\\x0b\\x0c\\x0e-\\x1f\\x21\\x23-\\x5b\\x5d-\\x7f]|\\\\[\\x01-\\x09\\x0b\\x0c\\x0e-\\x7f])*\")@(?:(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\\.)+[a-z0-9](?:[a-z0-9-]*[a-z0-9])?|\\[(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?|[a-z0-9-]*[a-z0-9]:(?:[\\x01-\\x08\\x0b\\x0c\\x0e-\\x1f\\x21-\\x5a\\x53-\\x7f]|\\\\[\\x01-\\x09\\x0b\\x0c\\x0e-\\x7f])+)\\])",
  re.IGNORECASE)


class SpacyNER(TextSignal):
  """Named entity recognition with spacy

  For details see: [spacy.io/models](https://spacy.io/models).
  """ # noqa: D415, D400
  name = 'spacy_ner'
  display_name = 'Spacy Named Entity Recognition'

  model: Optional[str] = PydanticField(
    title='SpaCy package name or model path.', default='en_core_web_sm', description='')

  input_type = SignalInputType.TEXT
  compute_type = SignalInputType.TEXT

  _nlp: spacy.language.Language

  @override
  def setup(self) -> None:
    self._nlp = spacy.load(
      'en_core_web_sm',
      # Disable everything except the NER component. See: https://spacy.io/models
      disable=['tok2vec', 'tagger', 'parser', 'attribute_ruler', 'lemmatizer'])

  @override
  def fields(self) -> Field:
    return field(fields=[field('string_span', fields={'label': 'string'})])

  @override
  def compute(self, data: Iterable[RichData]) -> Iterable[Optional[Item]]:
    text_data = (row if isinstance(row, str) else '' for row in data)

    for doc in self._nlp.pipe(text_data):
      result = [lilac_span(ent.start_char, ent.end_char, {'label': ent.label_}) for ent in doc.ents]

      if result:
        yield result
      else:
        yield None
