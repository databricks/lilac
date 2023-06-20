"""Compute text statistics for a document."""
from typing import Iterable, Optional, cast

import spacy
import textacy
from spacy import Language
from spacy.tokens import Doc
from textacy import text_stats
from typing_extensions import override

from ..schema import Field, Item, RichData, field
from ..utils import chunks
from .signal import TextSignal

SPACY_LANG_MODEL = 'en_core_web_sm'
SPACY_BATCH_SIZE = 128

NUM_CHARS = 'num_characters'
READABILITY = 'readability'
TYPE_TOKEN_RATIO = 'type_token_ratio'


class TextStatisticsSignal(TextSignal):
  """Compute text statistics for a document such as readability scores, type-token-ratio, etc.."""
  name = 'text_statistics'
  display_name = 'Text Statistics'

  _lang: Optional[Language] = None

  @override
  def fields(self) -> Field:
    return field(fields={
      NUM_CHARS: 'int32',
      READABILITY: 'float32',
      TYPE_TOKEN_RATIO: 'float32',
    })

  @override
  def setup(self) -> None:
    if not spacy.util.is_package(SPACY_LANG_MODEL):
      spacy.cli.download(SPACY_LANG_MODEL)
    self._lang = spacy.load(
      SPACY_LANG_MODEL,
      disable=[
        'parser', 'tagger', 'ner', 'lemmatizer', 'textcat', 'custom', 'tok2vec', 'attribute_ruler'
      ])

  @override
  def compute(self, data: Iterable[RichData]) -> Iterable[Optional[Item]]:
    for batch in chunks(data, SPACY_BATCH_SIZE):
      # Replace None with empty strings to avoid spacy errors.
      batch = [x or '' for x in batch]
      # See https://textacy.readthedocs.io/en/0.11.0/api_reference/text_stats.html for a list of
      # available statistics.
      corpus = textacy.Corpus(lang=self._lang, data=batch)
      for doc in cast(Iterable[Doc], corpus):
        if not len(doc):
          yield None
          continue
        readability = text_stats.readability.automated_readability_index(doc)
        ttr = text_stats.diversity.ttr(doc)
        num_chars = text_stats.basics.n_chars(doc)

        yield {
          NUM_CHARS: num_chars,
          READABILITY: readability,
          TYPE_TOKEN_RATIO: ttr,
        }
