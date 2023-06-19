"""Compute text statistics for a document."""
from typing import Iterable, Optional

import spacy
import textacy
from spacy import Language
from textacy import text_stats
from typing_extensions import override

from ..schema import Field, Item, RichData, field
from .signal import TextSignal

SPACY_LANG_MODEL = 'en_core_web_sm'

NUM_CHARS = 'num_characters'
READABILITY = 'readability'
TYPE_TOKEN_RATIO = 'type_token_ratio'


class TextStatisticsSignal(TextSignal):
  """Compute text statistics for a document."""
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
      SPACY_LANG_MODEL, disable=['parser', 'tagger', 'ner', 'lemmatizer', 'textcat', 'custom'])

  @override
  def compute(self, data: Iterable[RichData]) -> Iterable[Optional[Item]]:
    for text in data:
      if not isinstance(text, str):
        yield None
      doc = textacy.make_spacy_doc(text, lang=self._lang)
      readability = text_stats.readability.automated_readability_index(doc)
      ttr = text_stats.diversity.ttr(doc)
      yield {
        NUM_CHARS: len(text),
        READABILITY: readability,
        TYPE_TOKEN_RATIO: ttr,
      }
