"""Compute named entity recognition with SpaCy."""
from typing import TYPE_CHECKING, Iterable, Optional

from pydantic import Field as PydanticField
from typing_extensions import override

from ..data.dataset_utils import lilac_span
from ..schema import Field, Item, RichData, SignalInputType, field
from .signal import TextSignal

if TYPE_CHECKING:
  import spacy


class SpacyNER(TextSignal):
  """Named entity recognition with SpaCy.

  For details see: [spacy.io/models](https://spacy.io/models).
  """
  name = 'spacy_ner'
  display_name = 'Named Entity Recognition'

  model: Optional[str] = PydanticField(
    title='SpaCy package name or model path.', default='en_core_web_sm')

  input_type = SignalInputType.TEXT
  compute_type = SignalInputType.TEXT

  _nlp: 'spacy.language.Language'

  @override
  def setup(self) -> None:
    try:
      import spacy
    except ImportError:
      raise ImportError('Could not import the "spacy" python package. '
                        'Please install it with `pip install spacy`.')

    if not spacy.util.is_package(self.model):
      spacy.cli.download(self.model)
    self._nlp = spacy.load(
      self.model,
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
