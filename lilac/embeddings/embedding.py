"""Embedding registry."""
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Generator, Iterable, Optional, Union, cast

import numpy as np
from pydantic import StrictStr
from sklearn.preprocessing import normalize

from ..schema import (
  EMBEDDING_KEY,
  SPAN_KEY,
  TEXT_SPAN_END_FEATURE,
  TEXT_SPAN_START_FEATURE,
  EmbeddingInputType,
  Item,
  RichData,
  SpanVector,
  lilac_embedding,
)
from ..signal import TextEmbeddingSignal, get_signal_by_type
from ..splitters.chunk_splitter import TextChunk
from ..utils import chunks

EMBEDDING_SORT_PRIORITIES = ['gte-small', 'gte-base', 'openai', 'sbert']

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
        raise ValueError('Embedding signal returned None.')

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


def compute_split_embeddings(
  docs: Iterable[str],
  batch_size: int,
  embed_fn: Callable[[list[str]], list[np.ndarray]],
  split_fn: Optional[Callable[[str], list[TextChunk]]] = None,
  num_parallel_requests: int = 1,
) -> Generator[Item, None, None]:
  """Compute text embeddings in batches of chunks, using the provided splitter and embedding fn."""
  pool = ThreadPoolExecutor()

  def _splitter(doc: str) -> list[TextChunk]:
    if not doc:
      return []
    if split_fn:
      return split_fn(doc)
    else:
      # Return a single chunk that spans the entire document.
      return [(doc, (0, len(doc)))]

  num_docs = 0

  def _flat_split_batch_docs(docs: Iterable[str]) -> Generator[tuple[int, TextChunk], None, None]:
    """Split a batch of documents into chunks and yield them."""
    nonlocal num_docs
    for i, doc in enumerate(docs):
      num_docs += 1
      chunks = _splitter(doc)
      for chunk in chunks:
        yield (i, chunk)

  doc_chunks = _flat_split_batch_docs(docs)
  items_to_yield: Optional[list[Item]] = None
  current_index = 0

  mega_batch_size = batch_size * num_parallel_requests

  for batch in chunks(doc_chunks, mega_batch_size):
    texts = [text for _, (text, _) in batch]
    embeddings: list[np.ndarray] = []

    for x in list(pool.map(lambda x: embed_fn(x), chunks(texts, batch_size))):
      embeddings.extend(x)
    matrix = cast(np.ndarray, normalize(np.array(embeddings, dtype=np.float32)))
    # np.split returns a shallow copy of each embedding so we don't increase the mem footprint.
    embeddings_batch = cast(list[np.ndarray], np.split(matrix, matrix.shape[0]))
    for (index, (_, (start, end))), embedding in zip(batch, embeddings_batch):
      embedding = embedding.reshape(-1)
      if index == current_index:
        if items_to_yield is None:
          items_to_yield = []
        items_to_yield.append(lilac_embedding(start, end, embedding))
      else:
        yield items_to_yield
        current_index += 1
        while current_index < index:
          yield None
          current_index += 1
        items_to_yield = [lilac_embedding(start, end, embedding)]

  while current_index < num_docs:
    yield items_to_yield
    items_to_yield = None
    current_index += 1
