"""Compute text statistics for a document."""
from typing import TYPE_CHECKING, Iterable, Optional, cast

from typing_extensions import override

from ..schema import Field, Item, RichData, field
from ..utils import chunks
from .signal import TextSignal

SPACY_LANG_MODEL = 'en_core_web_sm'
SPACY_BATCH_SIZE = 128

NUM_CHARS = 'num_characters'
READABILITY = 'readability'
TYPE_TOKEN_RATIO = 'log(type_token_ratio)'

if TYPE_CHECKING:
  from spacy import Language
  from spacy.tokens import Doc


class TextStatisticsSignal(TextSignal):
  """Compute text statistics for a document such as readability scores, type-token-ratio, etc.."""
  name = 'text_statistics'
  display_name = 'Text Statistics'

  _lang: Optional['Language'] = None

  @override
  def fields(self) -> Field:
    return field(fields={
      NUM_CHARS: 'int32',
      READABILITY: 'float32',
      TYPE_TOKEN_RATIO: 'float32',
    })

  @override
  def setup(self) -> None:
    try:
      import spacy
    except ImportError:
      raise ImportError('Could not import the "spacy" python package. '
                        'Please install it with `pip install spacy`.')

    if not spacy.util.is_package(SPACY_LANG_MODEL):
      spacy.cli.download(SPACY_LANG_MODEL)
    self._lang = spacy.load(
      SPACY_LANG_MODEL,
      disable=[
        'parser', 'tagger', 'ner', 'lemmatizer', 'textcat', 'custom', 'tok2vec', 'attribute_ruler'
      ])

  @override
  def compute(self, data: Iterable[RichData]) -> Iterable[Optional[Item]]:
    try:
      import textacy
      from textacy import text_stats
    except ImportError:
      raise ImportError('Could not import the "textacy" python package. '
                        'Please install it with `pip install textacy`.')
    for batch in chunks(data, SPACY_BATCH_SIZE):
      # Replace None with empty strings to avoid spacy errors.
      batch = [x or '' for x in batch]
      # See https://textacy.readthedocs.io/en/0.11.0/api_reference/text_stats.html for a list of
      # available statistics.
      corpus = textacy.Corpus(lang=self._lang, data=batch)
      for doc in cast(Iterable['Doc'], corpus):
        if not len(doc):
          yield None
          continue
        readability = text_stats.readability.automated_readability_index(doc)
        ttr = text_stats.diversity.log_ttr(doc)
        num_chars = text_stats.basics.n_chars(doc)

        yield {
          NUM_CHARS: num_chars,
          READABILITY: readability,
          TYPE_TOKEN_RATIO: ttr,
        }
