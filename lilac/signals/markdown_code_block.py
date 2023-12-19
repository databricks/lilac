"""Finds markdown blocks.

NOTE: It would be great to use guesslang to detect the language automatically, however
there is a dependency conflict with typing extensions.
"""
import re
from typing import ClassVar, Iterable, Iterator, Optional, cast

from typing_extensions import override

from ..schema import Field, Item, RichData, field, span
from ..signal import TextSignal

markdown_block_re = re.compile('```([^\n ]*?)\n(.*?)\n```', re.MULTILINE | re.DOTALL)


class MarkdownCodeBlockSignal(TextSignal):
  """Finds markdown blocks in text. Emits the language of the block with the span."""

  name: ClassVar[str] = 'markdown_code_block'
  display_name: ClassVar[str] = 'Markdown Code Block Detection'

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
