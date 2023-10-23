"""SpaCy-based chunk splitting algorithms."""
import bisect
from typing import Callable, Optional, Sequence

import numpy as np
import spacy

from .chunk_splitter import TextChunk

# Make one lazy global instance; SpaCy sentencizers take 75ms merely to construct.
__SPACY_SENTENCIZER = None


def get_spacy() -> spacy.Language:
  """Lazily instantiate and return a singeton SpaCy sentencizer object."""
  global __SPACY_SENTENCIZER
  if __SPACY_SENTENCIZER is None:
    __SPACY_SENTENCIZER = spacy.blank('en')
    # This includes colon as a sentence boundary; LLM datasets tend to contain a lot of semantic
    # markers with a colon, like "Teacher: ... " or "Answer the following question: ..."
    __SPACY_SENTENCIZER.add_pipe('sentencizer', config={'punct_chars': [':', ';', '.', '!', '?']})
    # Increase the number of characters of the tokenizer as we're not using a parser or NER.
    __SPACY_SENTENCIZER.max_length = 10_000_000
  return __SPACY_SENTENCIZER


def simple_spacy_chunker(text: str, filter_short: int = 4) -> list[TextChunk]:
  """Split text into sentence-based chunks, using SpaCy."""
  sentencizer = get_spacy()
  chunks = [
    (text[s.start_char:s.end_char], (s.start_char, s.end_char)) for s in sentencizer(text).sents
  ]
  # Filter out stray whitespace, list numberings, etc.
  chunks = [c for c in chunks if len(c[0].strip()) > filter_short]
  return chunks


def group_by_embedding(fulltext: str, chunks: list[TextChunk], embed_fn: Callable[[list[str]],
                                                                                  list[np.ndarray]],
                       target_num_groups: int, max_len: int) -> list[TextChunk]:
  """Take a series of smaller chunks and cluster them together.

  Args:
    fulltext: Full text.
    chunks: Smaller chunks to combine.
    embed_fn: A function mapping strings to an embedding vector.
    target_num_groups: Target number of chunks in final output.
    max_len: Maximum size of a combined chunk.
  """
  embeddings = np.array(embed_fn([c[0] for c in chunks]))
  # Center the embeddings for all sentences; this accentuates sentence semantics,
  # especially if the entire passage is roughly about the same topic
  embeddings -= np.mean(embeddings, axis=0)

  neighbor_distances: Sequence[float] = (embeddings[:-1] * embeddings[1:]).sum(axis=1)
  potential_breaks: np.ndarray = np.array([c[1][1] for c in chunks[:-1]])  # end index of each chunk
  priority_sort_breaks: np.ndarray = potential_breaks[np.argsort(neighbor_distances)]

  # If there are fewer sentences than target number of groups, then this should degrade gracefully.
  breakpoints = [0] + sorted(priority_sort_breaks[:(target_num_groups - 1)]) + [chunks[-1][1][1]]

  def _find_long_spans(breakpoints: list[int]) -> Optional[tuple[int, int]]:
    for i, j in zip(breakpoints[:-1], breakpoints[1:]):
      if j - i > max_len:
        return (i, j)
    return None

  while (span := _find_long_spans(breakpoints)) is not None:
    i, j = span
    for potential_break in priority_sort_breaks:
      if i < potential_break < j:
        bisect.insort(breakpoints, potential_break)
        break
    else:  # No potential breaker was found. Arbitrarily split the span in half.
      bisect.insort(breakpoints, int((i + j) / 2))

  return [
    (fulltext[start:end], (start, end)) for start, end in zip(breakpoints[:-1], breakpoints[1:])
  ]


def clustering_spacy_chunker(
    text: str,
    filter_short: int = 4,
    max_len: int = 512,
    target_num_groups: Optional[int] = None,
    embed_fn: Optional[Callable[[list[str]], list[np.ndarray]]] = None) -> list[TextChunk]:
  """Split text into sentence-based chunks, with semantic clustering to join related sentences."""
  chunks = simple_spacy_chunker(text, filter_short=filter_short)
  if embed_fn is None:
    return chunks

  if target_num_groups is None:
    target_num_groups = int(
      (len(text)**0.33) / 1.5)  ## 1/3 power is eyeballed from texts spanning 50-5000 in len.
  return group_by_embedding(text, chunks, embed_fn, target_num_groups, max_len)
