"""Implementation of splitting text that looks at characters.

Recursively tries to split by different characters to find one that works.

The implementation below is forked from the LangChain project with the MIT license below.
See `RecursiveCharacterTextSplitter` in
https://github.com/hwchase17/langchain/blob/master/langchain/text_splitter.py
"""

# The MIT License

# Copyright (c) Harrison Chase

# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

from typing import Any, Callable, Iterable, Optional

from pydantic import validator
from typing_extensions import override

from ...data.dataset_utils import lilac_span
from ...schema import Item, RichData
from ...utils import log
from ..signal import TextSplitterSignal

TextChunk = tuple[str, tuple[int, int]]

DEFAULT_SEPARATORS = ['\n\n', '\n', ' ', '']


class ChunkSplitter(TextSplitterSignal):
  """Recursively split documents by different characters to find one that works."""

  name = 'chunk'
  display_name = 'Chunk Splitter'

  chunk_size: int = 200
  chunk_overlap: int = 50
  separators: list[str] = DEFAULT_SEPARATORS

  _length_function: Callable[[str], int] = len

  @validator('chunk_overlap')
  def check_overlap_smaller_than_chunk(cls, chunk_overlap: int, values: dict[str, Any]) -> int:
    """Check that the chunk overlap is smaller than the chunk size."""
    chunk_size: int = values['chunk_size']
    if chunk_overlap > chunk_size:
      raise ValueError(f'Got a larger chunk overlap ({chunk_overlap}) than chunk size '
                       f'({chunk_size}), should be smaller.')
    return chunk_overlap

  @validator('separators')
  def check_separators_are_strings(cls, separators: list[str]) -> list[str]:
    """Check that the separators are strings."""
    separators = list(separators) or DEFAULT_SEPARATORS
    for sep in separators:
      if not isinstance(sep, str):
        raise ValueError(f'Got separator {sep} that is not a string.')
    return separators

  @override
  def compute(self, data: Iterable[RichData]) -> Iterable[Optional[Item]]:
    for text in data:
      if not isinstance(text, str):
        yield None
        continue

      chunks = self._split_text(text)
      if not chunks:
        yield None
        continue

      yield [lilac_span(start, end) for _, (start, end) in chunks]

  def _sep_split(self, text: str, separator: str) -> list[TextChunk]:
    if separator == '':
      # We need to split by char.
      return [(letter, (i, i + 1)) for i, letter in enumerate(text)]

    offset = 0
    chunks: list[TextChunk] = []
    end_index = text.find(separator, offset)

    while end_index >= 0:
      chunks.append((text[offset:end_index], (offset, end_index)))
      offset = end_index + len(separator)
      end_index = text.find(separator, offset)

    # Append the last chunk.
    chunks.append((text[offset:], (offset, len(text))))

    return chunks

  def _split_text(self, text: str) -> list[TextChunk]:
    """Split incoming text and return chunks."""
    final_chunks: list[TextChunk] = []
    # Get appropriate separator to use
    separator = self.separators[-1]
    for _s in self.separators:
      if _s == '':
        separator = _s
        break
      if _s in text:
        separator = _s
        break
    # Now that we have the separator, split the text.
    splits = self._sep_split(text, separator)
    # Now go merging things, recursively splitting longer texts.
    good_splits: list[TextChunk] = []
    for chunk in splits:
      text_chunk, (start, _) = chunk
      if self._length_function(text_chunk) < self.chunk_size:
        good_splits.append(chunk)
      else:
        if good_splits:
          merged_text = self._merge_splits(good_splits, separator)
          final_chunks.extend(merged_text)
          good_splits = []
        other_chunks = self._split_text(text_chunk)
        # Adjust the offsets of the other chunks.
        other_chunks = [(t, (s + start, e + start)) for t, (s, e) in other_chunks]
        final_chunks.extend(other_chunks)
    if good_splits:
      merged_text = self._merge_splits(good_splits, separator)
      final_chunks.extend(merged_text)
    return final_chunks

  def _join_chunks(self, chunks: list[TextChunk], separator: str) -> Optional[TextChunk]:
    text = separator.join([text for text, _ in chunks])
    text = text.strip()
    if text == '':
      return None

    _, (first_span_start, _) = chunks[0]
    _, (_, last_span_end) = chunks[-1]
    return (text, (first_span_start, last_span_end))

  def _merge_splits(self, splits: Iterable[TextChunk], separator: str) -> list[TextChunk]:
    # We now want to combine these smaller pieces into medium size
    # chunks to send to the LLM.
    separator_len = self._length_function(separator)

    docs: list[TextChunk] = []
    current_doc: list[TextChunk] = []
    total = 0
    for chunk in splits:
      text_chunk, _ = chunk
      _len = self._length_function(text_chunk)
      if (total + _len + (separator_len if len(current_doc) > 0 else 0) > self.chunk_size):
        if total > self.chunk_size:
          log(f'Created a chunk of size {total}, '
              f'which is longer than the specified {self.chunk_size}')
        if len(current_doc) > 0:
          doc = self._join_chunks(current_doc, separator)
          if doc is not None:
            docs.append(doc)
          # Keep on popping if:
          # - we have a larger chunk than in the chunk overlap
          # - or if we still have any chunks and the length is long
          while total > self.chunk_overlap or (
              total + _len +
            (separator_len if len(current_doc) > 0 else 0) > self.chunk_size and total > 0):
            total -= self._length_function(current_doc[0][0]) + (
              separator_len if len(current_doc) > 1 else 0)
            current_doc = current_doc[1:]
      current_doc.append(chunk)
      total += _len + (separator_len if len(current_doc) > 1 else 0)
    doc = self._join_chunks(current_doc, separator)
    if doc is not None:
      docs.append(doc)
    return docs
