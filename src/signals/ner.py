"""Compute named entity recognition with SpaCy."""
from importlib import import_module
from typing import Any, Iterable, Optional

import spacy
from pydantic import Field as PydanticField
from spacy import Language
from spacy.cli import download
from typing_extensions import override

from ..data.dataset_utils import lilac_span
from ..schema import Field, Item, RichData, SignalInputType, field
from .signal import TextSignal


# Taken from https://github.com/BramVanroy/spacy_download/blob/main/src/spacy_download/load.py
def load_spacy(model_name: str, **kwargs: dict[Any, Any]) -> Language:
  """Load a spaCy model, download it if it has not been installed yet.

  :param model_name: the model name, e.g., en_core_web_sm
  :param kwargs: options passed to the spaCy loader, such as component exclusion, as you
  would with spacy.load()
  :return: an initialized spaCy Language
  :raises: SystemExit: if the model_name cannot be downloaded.
  """
  try:
    model_module = import_module(model_name)
  except ModuleNotFoundError:
    download(model_name)
    model_module = import_module(model_name)

  return model_module.load(**kwargs)


class SpacyNER(TextSignal):
  """Named entity recognition with SpaCy

  For details see: [spacy.io/models](https://spacy.io/models).
  """ # noqa: D415, D400
  name = 'spacy_ner'
  display_name = 'Named Entity Recognition'

  model: Optional[str] = PydanticField(
    title='SpaCy package name or model path.', default='en_core_web_sm')

  input_type = SignalInputType.TEXT
  compute_type = SignalInputType.TEXT

  _nlp: spacy.language.Language

  @override
  def setup(self) -> None:
    self._nlp = load_spacy(
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
