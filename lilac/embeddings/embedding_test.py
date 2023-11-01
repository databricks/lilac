"""Tests for embedding.py."""

import numpy as np

from ..schema import lilac_embedding
from ..splitters.chunk_splitter import TextChunk
from .embedding import compute_split_embeddings


def char_splitter(text: str) -> list[TextChunk]:
  return [(letter, (i, i + 1)) for i, letter in enumerate(text)]


def test_split_and_combine_text_embeddings_batch_across_two_docs() -> None:
  docs = ['This is', '123']
  batch_size = 3

  embed_fn_inputs: list[list[str]] = []

  def embed_fn(batch: list[str]) -> list[np.ndarray]:
    embed_fn_inputs.append(batch)
    return [np.ones(1) for _ in batch]

  result = list(compute_split_embeddings(docs, batch_size, embed_fn, char_splitter))

  # Each input to embed_fn is a batch of at most 3 letters.
  assert embed_fn_inputs == [['T', 'h', 'i'], ['s', ' ', 'i'], ['s', '1', '2'], ['3']]

  assert result == [
    [
      lilac_embedding(0, 1, np.array(1)),  # T
      lilac_embedding(1, 2, np.array(1)),  # h
      lilac_embedding(2, 3, np.array(1)),  # i
      lilac_embedding(3, 4, np.array(1)),  # s
      lilac_embedding(4, 5, np.array(1)),  # ' '
      lilac_embedding(5, 6, np.array(1)),  # i
      lilac_embedding(6, 7, np.array(1)),  # s
    ],
    [
      lilac_embedding(0, 1, np.array(1)),  # 1
      lilac_embedding(1, 2, np.array(1)),  # 2
      lilac_embedding(2, 3, np.array(1)),  # 3
    ],
  ]


def test_split_and_combine_text_embeddings_no_docs() -> None:
  docs: list[str] = []
  batch_size = 3

  embed_fn_inputs: list[list[str]] = []

  def embed_fn(batch: list[str]) -> list[np.ndarray]:
    embed_fn_inputs.append(batch)
    return [np.ones(1) for _ in batch]

  result = list(compute_split_embeddings(docs, batch_size, embed_fn, char_splitter))
  assert embed_fn_inputs == []
  assert result == []


def test_split_and_combine_text_embeddings_empty_docs() -> None:
  docs: list[str] = ['', '', '123']
  batch_size = 3

  embed_fn_inputs: list[list[str]] = []

  def embed_fn(batch: list[str]) -> list[np.ndarray]:
    embed_fn_inputs.append(batch)
    return [np.ones(1) for _ in batch]

  result = list(compute_split_embeddings(docs, batch_size, embed_fn, char_splitter))
  assert embed_fn_inputs == [['1', '2', '3']]

  assert result == [
    None,
    None,
    [
      lilac_embedding(0, 1, np.array(1)),  # 1
      lilac_embedding(1, 2, np.array(1)),  # 2
      lilac_embedding(2, 3, np.array(1)),  # 3
    ],
  ]


def test_split_and_combine_text_embeddings_empty_docs_at_end() -> None:
  docs: list[str] = ['123', '', '']
  batch_size = 3

  embed_fn_inputs: list[list[str]] = []

  def embed_fn(batch: list[str]) -> list[np.ndarray]:
    embed_fn_inputs.append(batch)
    return [np.ones(1) for _ in batch]

  result = list(compute_split_embeddings(docs, batch_size, embed_fn, char_splitter))
  assert embed_fn_inputs == [['1', '2', '3']]

  assert result == [
    [
      lilac_embedding(0, 1, np.array(1)),  # 1
      lilac_embedding(1, 2, np.array(1)),  # 2
      lilac_embedding(2, 3, np.array(1)),  # 3
    ],
    None,
    None,
  ]
