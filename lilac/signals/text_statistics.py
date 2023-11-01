"""Compute text statistics for a document."""
from typing import TYPE_CHECKING, ClassVar, Iterable, Optional, cast

from typing_extensions import override

from ..schema import Field, Item, RichData, field
from ..signal import TextSignal
from ..utils import chunks

SPACY_LANG_MODEL = 'en_core_web_sm'
SPACY_BATCH_SIZE = 128
SPACY_MAX_LENGTH = 2_000_000

NUM_CHARS = 'num_characters'
READABILITY = 'readability'
TYPE_TOKEN_RATIO = 'log(type_token_ratio)'
FRAC_NON_ASCII = 'frac_non_ascii'

if TYPE_CHECKING:
  from spacy import Language
  from spacy.tokens import Doc


class TextStatisticsSignal(TextSignal):
  """Compute text statistics for a document such as readability scores, type-token-ratio, etc.."""

  name: ClassVar[str] = 'text_statistics'
  display_name: ClassVar[str] = 'Text Statistics'

  _lang: Optional['Language'] = None

  @override
  def fields(self) -> Field:
    return field(
      fields={
        NUM_CHARS: 'int32',
        READABILITY: 'float32',
        TYPE_TOKEN_RATIO: 'float32',
        FRAC_NON_ASCII: field(
          'float32', bins=[('Low', None, 0.15), ('Medium', 0.15, 0.3), ('High', 0.3, None)]
        ),
      }
    )

  @override
  def setup(self) -> None:
    try:
      import spacy
      import spacy.cli
      import spacy.util
    except ImportError:
      raise ImportError(
        'Could not import the "spacy" python package. '
        'Please install it with `pip install spacy`.'
      )

    if not spacy.util.is_package(SPACY_LANG_MODEL):
      spacy.cli.download(SPACY_LANG_MODEL)
    self._lang = spacy.load(
      SPACY_LANG_MODEL,
      disable=[
        'parser',
        'tagger',
        'ner',
        'lemmatizer',
        'textcat',
        'custom',
        'tok2vec',
        'attribute_ruler',
      ],
    )
    self._lang.max_length = SPACY_MAX_LENGTH

  @override
  def compute(self, data: Iterable[RichData]) -> Iterable[Optional[Item]]:
    try:
      import textacy.corpus
      from textacy import text_stats
    except ImportError:
      raise ImportError(
        'Could not import the "textacy" python package. '
        'Please install it with `pip install textacy`.'
      )
    if not self._lang:
      raise RuntimeError('Language model was not loaded.')

    data = cast(Iterable[str], data)
    for batch in chunks(data, SPACY_BATCH_SIZE):
      # Replace None with empty strings to avoid spacy errors.
      batch = [x or '' for x in batch]
      # See https://textacy.readthedocs.io/en/0.11.0/api_reference/text_stats.html for a list of
      # available statistics.
      corpus = textacy.corpus.Corpus(lang=self._lang, data=batch)
      for doc in cast(Iterable['Doc'], corpus):
        if not doc or not doc.text.strip():
          yield None
          continue
        try:
          readability = text_stats.readability.automated_readability_index(doc)
        except ZeroDivisionError:
          readability = None
        try:
          ttr = text_stats.diversity.log_ttr(doc)
        except ValueError:
          ttr = None
        num_chars = len(doc.text)
        num_non_ascii = 0
        for c in doc.text:
          if ord(c) >= 128:
            num_non_ascii += 1
        frac_non_ascii = num_non_ascii / num_chars if num_chars else 0

        yield {
          NUM_CHARS: num_chars,
          READABILITY: readability,
          TYPE_TOKEN_RATIO: ttr,
          FRAC_NON_ASCII: frac_non_ascii,
        }
