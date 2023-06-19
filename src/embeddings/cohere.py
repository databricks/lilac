"""Cohere embeddings."""
import functools
from typing import Iterable, cast

import cohere
import numpy as np
from typing_extensions import override

from ..config import CONFIG
from ..schema import Item, RichData
from ..signals.signal import TextEmbeddingSignal
from ..signals.splitters.chunk_splitter import TextChunk, split_text
from .embedding import split_and_combine_text_embeddings

NUM_PARALLEL_REQUESTS = 10
COHERE_BATCH_SIZE = 96


@functools.cache
def _cohere() -> cohere.Client:
  api_key = CONFIG['COHERE_API_KEY']
  if not api_key:
    raise ValueError('`COHERE_API_KEY` environment variable not set.')
  return cohere.Client(api_key, max_retries=10)


class Cohere(TextEmbeddingSignal):
  """Computes embeddings using Cohere's embedding API.

  <br>**Important**: This will send data to an external server!

  <br>To use this signal, you must get a Cohere API key from
  [cohere.com/embed](https://cohere.com/embed) and add it to your .env.local.

  <br>For details on pricing, see: https://cohere.com/pricing.
  """

  name = 'cohere'
  display_name = 'Cohere Embeddings'

  @override
  def compute(self, docs: Iterable[RichData]) -> Iterable[Item]:
    """Compute embeddings for the given documents."""

    def splitter(doc: str) -> list[TextChunk]:
      if doc is None:
        return []
      if self._split:
        return split_text(doc)
      else:
        # Return a single chunk that spans the entire document.
        return [(doc, (0, len(doc)))]

    def embed_fn(texts: list[str]) -> list[np.ndarray]:
      return _cohere().embed(texts, truncate='END').embeddings

    docs = cast(Iterable[str], docs)
    yield from split_and_combine_text_embeddings(
      docs, COHERE_BATCH_SIZE, splitter, embed_fn, num_parallel_requests=NUM_PARALLEL_REQUESTS)
