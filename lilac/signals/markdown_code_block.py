"""Finds markdown code blocks.

NOTE: It would be great to use guesslang to detect the language automatically, however
there is a dependency conflict with typing extensions.
"""
import re
from typing import ClassVar, Iterable, Iterator, Optional, cast

from typing_extensions import override

from ..schema import Field, Item, RichData, field, span
from ..signal import TextSignal

MARKDOWN_RE = '```([^\n ]*?)\n(.*?)\n```'


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
    markdown_re = re.compile(MARKDOWN_RE, re.MULTILINE | re.DOTALL)
    for doc in data:
      text = cast(str, doc)
      # Get the spans
      markdown_re_spans = markdown_re.finditer(text)
      languages = markdown_re.findall(text)

      spans: list[Item] = []
      for re_span, (language, _) in zip(markdown_re_spans, languages):
        spans.append(span(re_span.start(), re_span.end(), {'language': language}))

      yield spans
