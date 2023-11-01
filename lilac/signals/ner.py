"""Compute named entity recognition with SpaCy."""
from typing import TYPE_CHECKING, ClassVar, Iterable, Optional

from pydantic import Field as PydanticField
from typing_extensions import override

from ..schema import Field, Item, RichData, SignalInputType, field, lilac_span
from ..signal import TextSignal

if TYPE_CHECKING:
  import spacy


class SpacyNER(TextSignal):
  """Named entity recognition with SpaCy.

  For details see: [spacy.io/models](https://spacy.io/models).
  """

  name: ClassVar[str] = 'spacy_ner'
  display_name: ClassVar[str] = 'Named Entity Recognition'
  input_type: ClassVar[SignalInputType] = SignalInputType.TEXT

  model: str = PydanticField(title='SpaCy package name or model path.', default='en_core_web_sm')

  _nlp: Optional['spacy.language.Language'] = None

  @override
  def setup(self) -> None:
    try:
      import spacy
      import spacy.cli
    except ImportError:
      raise ImportError(
        'Could not import the "spacy" python package. '
        'Please install it with `pip install spacy`.'
      )

    if not spacy.util.is_package(self.model):
      spacy.cli.download(self.model)
    self._nlp = spacy.load(
      self.model,
      # Disable everything except the NER component. See: https://spacy.io/models
      disable=['tok2vec', 'tagger', 'parser', 'attribute_ruler', 'lemmatizer'],
    )

  @override
  def fields(self) -> Field:
    return field(fields=[field('string_span', fields={'label': 'string'})])

  @override
  def compute(self, data: Iterable[RichData]) -> Iterable[Optional[Item]]:
    if not self._nlp:
      raise RuntimeError('SpaCy model is not initialized.')

    text_data = (row if isinstance(row, str) else '' for row in data)

    for doc in self._nlp.pipe(text_data):
      result = [lilac_span(ent.start_char, ent.end_char, {'label': ent.label_}) for ent in doc.ents]

      if result:
        yield result
      else:
        yield None
