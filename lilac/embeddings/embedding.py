"""Embedding registry."""
from typing import Callable, Iterable, Optional, Union

import numpy as np
from pydantic import StrictStr

from ..schema import (
  EMBEDDING_KEY,
  SPAN_KEY,
  TEXT_SPAN_END_FEATURE,
  TEXT_SPAN_START_FEATURE,
  EmbeddingInputType,
  Item,
  RichData,
  SpanVector,
  chunk_embedding,
)
from ..signal import TextEmbeddingSignal, get_signal_by_type
from ..splitters.chunk_splitter import TextChunk
from ..utils import chunks

EMBEDDING_SORT_PRIORITIES = [
  'gte-small',
  'gte-base',
  'gte-large',
  'jina-v2-small',
  'jina-v2-base',
  'openai',
  'sbert',
]

EmbeddingId = Union[StrictStr, TextEmbeddingSignal]

EmbedFn = Callable[[Iterable[RichData]], Iterable[list[SpanVector]]]


def get_embed_fn(
  embedding_name: str, split: bool, input_type: EmbeddingInputType = 'document'
) -> EmbedFn:
  """Return a function that returns the embedding matrix for the given embedding signal."""
  embedding_cls = get_signal_by_type(embedding_name, TextEmbeddingSignal)
  embedding = embedding_cls(split=split, embed_input_type=input_type)
  embedding.setup()

  def _embed_fn(data: Iterable[RichData]) -> Iterable[list[SpanVector]]:
    items = embedding.compute(data)

    for item in items:
      if not item:
        raise ValueError('Embedding signal returned None.', embedding)

      yield [
        {
          'vector': item_val[EMBEDDING_KEY].reshape(-1),
          'span': (
            item_val[SPAN_KEY][TEXT_SPAN_START_FEATURE],
            item_val[SPAN_KEY][TEXT_SPAN_END_FEATURE],
          ),
        }
        for item_val in item
      ]

  return _embed_fn


def identity_chunker(doc: str) -> list[TextChunk]:
  """Split a document into a single chunk."""
  return [(doc, (0, len(doc)))]


def chunked_compute_embedding(
  embed_fn: Callable[[list[str]], list[np.ndarray]],
  docs: list[str],
  batch_size: int,
  chunker: Callable[[str], list[TextChunk]] = identity_chunker,
) -> list[Optional[list[Item]]]:
  """Compute text embeddings for chunks of text, using the provided splitter and embedding fn."""
  text_chunks = [(i, chunk) for i, doc in enumerate(docs) for chunk in chunker(doc)]
  output: list[list[Item]] = [[] for _ in docs]
  batches = chunks(text_chunks, batch_size)
  for batch in batches:
    batch_texts = [text for _, (text, _) in batch]
    batch_embeddings = embed_fn(batch_texts)
    for (i, (_, (start, end))), embedding in zip(batch, batch_embeddings):
      output[i].append(chunk_embedding(start, end, embedding))

  return [lis or None for lis in output]
