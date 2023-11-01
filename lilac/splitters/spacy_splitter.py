"""SpaCy-based chunk splitting algorithms."""
import bisect
import functools
from typing import Optional, Sequence

import numpy as np
import spacy
import tiktoken

from .chunk_splitter import TextChunk

# Vector size to use for chunk comparisons.
BOW_VECTOR_SIZE = 128


@functools.cache
def get_tokenizer() -> tiktoken.Encoding:
  """Lazily instantiate and return a singleton TikToken tokenizer object."""
  return tiktoken.get_encoding('cl100k_base')


def embed_tokenizer_BoW(texts: list[str]) -> np.ndarray:
  """Encode a list of texts as a bag-of-words vector."""
  tokenizer = get_tokenizer()
  out = np.zeros((len(texts), BOW_VECTOR_SIZE), dtype=np.float32)
  for i, text in enumerate(texts):
    token_ids = np.array(tokenizer.encode(text)) % BOW_VECTOR_SIZE
    out[i] = np.bincount(token_ids, minlength=BOW_VECTOR_SIZE)
  return out


@functools.cache
def get_spacy() -> spacy.Language:
  """Lazily instantiate and return a singeton SpaCy sentencizer object."""
  sentencizer = spacy.blank('en')
  # This includes colon as a sentence boundary; LLM datasets tend to contain a lot of semantic
  # markers with a colon, like "Teacher: ... " or "Answer the following question: ..."
  sentencizer.add_pipe('sentencizer', config={'punct_chars': [':', ';', '.', '!', '?']})
  # Increase the number of characters of the tokenizer as we're not using a parser or NER.
  sentencizer.max_length = 10_000_000
  return sentencizer


def simple_spacy_chunker(text: str, filter_short: int = 4) -> list[TextChunk]:
  """Split text into sentence-based chunks, using SpaCy."""
  sentencizer = get_spacy()
  chunks = [
    (text[s.start_char : s.end_char], (s.start_char, s.end_char)) for s in sentencizer(text).sents
  ]
  # Filter out stray whitespace, list numberings, etc.
  chunks = [c for c in chunks if len(c[0].strip()) > filter_short]
  return chunks


def group_by_embedding(
  fulltext: str, chunks: list[TextChunk], target_num_groups: int, max_len: int
) -> list[TextChunk]:
  """Take a series of smaller chunks and cluster them together.

  Args:
    fulltext: Full text.
    chunks: Smaller chunks to combine.
    embed_fn: A function mapping strings to an embedding vector.
    target_num_groups: Target number of chunks in final output.
    max_len: Maximum size of a combined chunk.
  """
  if not chunks:
    return []

  texts = [c[0] for c in chunks]
  embeddings = embed_tokenizer_BoW(texts)
  # Center the embeddings for all sentences; this accentuates sentence semantics,
  # especially if the entire passage is roughly about the same topic
  embeddings -= np.mean(embeddings, axis=0)
  # Add a small amount of noise to prevent division by zero.
  embeddings += np.random.uniform(size=embeddings.shape) * 1e-6
  embeddings /= np.linalg.norm(embeddings, axis=-1, keepdims=True)

  neighbor_distances: Sequence[float] = (embeddings[:-1] * embeddings[1:]).sum(axis=1)
  potential_breaks: np.ndarray = np.array([c[1][1] for c in chunks[:-1]])  # end index of each chunk
  priority_sort_breaks: np.ndarray = potential_breaks[np.argsort(neighbor_distances)]

  # If there are fewer sentences than target number of groups, then this should degrade gracefully.
  breakpoints = [0] + sorted(priority_sort_breaks[: (target_num_groups - 1)]) + [chunks[-1][1][1]]

  def _find_long_spans(breakpoints: list[int]) -> Optional[tuple[int, int]]:
    for i, j in zip(breakpoints[:-1], breakpoints[1:]):
      if j - i > max_len:
        return (i, j)
    return None

  # Recursively break long spans until there are no more.
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
  text: str, filter_short: int = 4, max_len: int = 512, target_num_groups: Optional[int] = None
) -> list[TextChunk]:
  """Split text into sentence-based chunks, with semantic clustering to join related sentences."""
  chunks = simple_spacy_chunker(text, filter_short=filter_short)

  if target_num_groups is None:
    # A rough heuristic for picking a number of target chunks.
    # These magic numbers were chosen by manually chunking 40 texts spanning 50-5000 characters in
    # length, and eyeballing a best-fit line from #num chunks vs. #length on a log-log plot.
    target_num_groups = max(1, int((len(text) ** 0.33) / 1.5))
  return group_by_embedding(text, chunks, target_num_groups, max_len)
