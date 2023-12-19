"""Finds markdown blocks."""
import re
from typing import TYPE_CHECKING, ClassVar, Iterable, Iterator, Optional, cast

from typing_extensions import override

from ..schema import Field, Item, RichData, field, span
from ..signal import TextSignal

SPACY_LANG_MODEL = 'en_core_web_sm'
SPACY_BATCH_SIZE = 128
SPACY_MAX_LENGTH = 2_000_000

NUM_CHARS = 'num_characters'
READABILITY = 'readability'
TYPE_TOKEN_RATIO = 'log(type_token_ratio)'
FRAC_NON_ASCII = 'frac_non_ascii'


if TYPE_CHECKING:
  pass

markdown_block_re = re.compile('```([^\n ]*?)\n(.*?)\n```', re.MULTILINE | re.DOTALL)


class MarkdownExtractorSignal(TextSignal):
  """Finds markdown blocks in text. Emits the language of the block with the span."""

  name: ClassVar[str] = 'markdown_extractor'
  display_name: ClassVar[str] = 'Markdown Extractor'

  @override
  def fields(self) -> Field:
    return field(
      fields=[
        field(
          dtype='string_span',
          fields={'language': 'string'},
        )
      ]
    )

  @override
  def compute(self, data: Iterable[RichData]) -> Iterator[Optional[Item]]:
    for doc in data:
      text = cast(str, doc)
      # Get the spans
      markdown_re_spans = markdown_block_re.finditer(text)
      languages = markdown_block_re.findall(text)

      spans: list[Item] = []
      for re_span, (language, _) in zip(markdown_re_spans, languages):
        spans.append(span(re_span.start(), re_span.end(), {'language': language}))

      yield spans
