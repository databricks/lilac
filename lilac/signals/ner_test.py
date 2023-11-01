"""Test the Spacy NER signal."""

from ..schema import field
from ..splitters.text_splitter_test_utils import text_to_expected_spans
from .ner import SpacyNER


def test_spacy_ner_fields() -> None:
  signal = SpacyNER()
  signal.setup()
  assert signal.fields() == field(fields=[field('string_span', fields={'label': 'string'})])


def test_ner() -> None:
  signal = SpacyNER()
  signal.setup()

  text = (
    'Net income was $9.4 million compared to the prior year of $2.7 million.'
    'Revenue exceeded twelve billion dollars, with a loss of $1b.'
  )
  emails = list(signal.compute([text]))

  expected_spans = text_to_expected_spans(
    text,
    [
      ('$9.4 million', {'label': 'MONEY'}),
      ('the prior year', {'label': 'DATE'}),
      ('$2.7 million', {'label': 'MONEY'}),
      ('twelve billion dollars', {'label': 'MONEY'}),
      ('1b', {'label': 'MONEY'}),
    ],
  )

  assert emails == [expected_spans]
