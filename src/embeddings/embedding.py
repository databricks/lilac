"""Embedding registry."""
from typing import Callable, Generator, Iterable, Union, cast

import numpy as np
from pydantic import StrictStr
from sklearn.preprocessing import normalize

from ..data.dataset_utils import lilac_embedding
from ..schema import Item, RichData
from ..signals.signal import EMBEDDING_KEY, TextEmbeddingSignal, get_signal_by_type
from ..signals.splitters.chunk_splitter import TextChunk
from ..utils import chunks

EmbeddingId = Union[StrictStr, TextEmbeddingSignal]

EmbedFn = Callable[[Iterable[RichData]], np.ndarray]


def get_embed_fn(embedding_name: str) -> EmbedFn:
  """Return a function that returns the embedding matrix for the given embedding signal."""
  embedding = get_signal_by_type(embedding_name, TextEmbeddingSignal)(split=False)

  def _embed_fn(data: Iterable[RichData]) -> np.ndarray:
    items = embedding.compute(data)

    embedding_vectors: list[np.ndarray] = []
    for item in items:
      if not item:
        raise ValueError('Embedding signal returned None.')
      if len(item) != 1:
        raise ValueError(
          f'Embedding signal returned {len(item)} items, but expected 1 since split was False')
      embedding_vector = item[0][EMBEDDING_KEY]
      if not isinstance(embedding_vector, np.ndarray):
        raise ValueError(
          f'Embedding signal returned {type(embedding_vector)} which is not an ndarray.')
      # We use squeeze here because embedding functions can return outer dimensions of 1.
      embedding_vector = embedding_vector.squeeze()
      if embedding_vector.ndim != 1:
        raise ValueError(f'Expected embeddings to be 1-dimensional, got {embedding_vector.ndim} '
                         f'with shape {embedding_vector.shape}.')
      embedding_vectors.append(embedding_vector)
    return np.array(embedding_vectors)

  return _embed_fn


def split_and_combine_text_embeddings(
    docs: Iterable[str], batch_size: int, splitter: Callable[[str], list[TextChunk]],
    embed_fn: Callable[[list[str]], list[np.ndarray]]) -> Generator[Item, None, None]:
  """Compute text embeddings in batches of chunks, using the provided splitter and embedding fn."""

  def _flat_split_batch_docs(docs: Iterable[str]) -> Generator[tuple[int, TextChunk], None, None]:
    """Split a batch of documents into chunks and yield them."""
    for i, doc in enumerate(docs):
      chunks = splitter(doc)
      for chunk in chunks:
        yield (i, chunk)

  doc_chunks = _flat_split_batch_docs(docs)
  items_to_yield: list[Item] = []
  current_index = 0

  for batch in chunks(doc_chunks, batch_size):
    texts = [text for _, (text, _) in batch]
    matrix = normalize(np.array(embed_fn(texts))).astype(np.float16)
    # np.split returns a shallow copy of each embedding so we don't increase the mem footprint.
    embeddings_batch = cast(list[np.ndarray], np.split(matrix, matrix.shape[0]))
    for (index, (_, (start, end))), embedding in zip(batch, embeddings_batch):
      if index == current_index:
        items_to_yield.append(lilac_embedding(start, end, embedding))
      else:
        yield items_to_yield
        items_to_yield = [lilac_embedding(start, end, embedding)]
        current_index = index

  # Yield the last batch.
  if items_to_yield:
    yield items_to_yield
