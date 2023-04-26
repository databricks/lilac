"""An embedding indexer that stores the embedding index on disk."""
import functools
import math
import os
import pathlib
from typing import Iterable, Optional, Union

import numpy as np
import pandas as pd
from typing_extensions import override

from ..schema import Path, PathTuple, RichData, normalize_path, path_to_alias
from ..tasks import TaskId, progress
from ..utils import chunks, file_exists, open_file
from .embedding_index import (
    EmbeddingIndex,
    EmbeddingIndexer,
    EmbeddingIndexerManifest,
    EmbeddingIndexInfo,
)
from .embedding_registry import EmbeddingId, get_embedding_cls

NP_INDEX_KEYS_KWD = 'keys'
NP_EMBEDDINGS_KWD = 'embeddings'


class EmbeddingIndexerDisk(EmbeddingIndexer):
  """An embedding indexer that stores the embedding index on disk."""

  def __init__(self, dataset_path: Union[str, pathlib.Path]) -> None:
    self.dataset_path = dataset_path

  @override
  def manifest(self) -> EmbeddingIndexerManifest:
    index_filenames: list[str] = []
    for root, _, files in os.walk(self.dataset_path):
      for file in files:
        if file.endswith(EMBEDDING_INDEX_INFO_SUFFIX):
          index_filenames.append(file)

    return EmbeddingIndexerManifest(indexes=self._read_index_infos(tuple(index_filenames)))

  @functools.cache
  def _read_index_infos(self, index_filenames: tuple[str]) -> list[EmbeddingIndexInfo]:
    index_infos: list[EmbeddingIndexInfo] = []
    for index_filename in index_filenames:
      with open_file(os.path.join(self.dataset_path, index_filename), 'r') as f:
        index_info = EmbeddingIndexInfo.parse_raw(f.read())
        index_infos.append(index_info)
    return index_infos

  @override
  def get_embedding_index(self, column: Path, embedding: EmbeddingId) -> EmbeddingIndex:
    if isinstance(embedding, str):
      embedding_name = embedding
    else:
      embedding_name = embedding.name

    path = normalize_path(column)
    index_filename = embedding_index_filename(path, embedding_name)
    index_path = os.path.join(self.dataset_path, index_filename)

    if not file_exists(index_path):
      raise ValueError(
          F'Embedding index for column "{path}" and embedding "{embedding_name}" does not exist. '
          'Please run "db.compute_embedding_index" on the database first.')

    # Read the embedding index from disk.
    with open_file(index_path, 'rb') as f:
      np_index: dict[str, np.ndarray] = np.load(f, allow_pickle=True)
      embeddings = np_index[NP_EMBEDDINGS_KWD]
      index_keys = np_index[NP_INDEX_KEYS_KWD].tolist()

    return EmbeddingIndex(path=index_path, keys=index_keys, embeddings=embeddings)

  @override
  def compute_embedding_index(self,
                              column: Path,
                              embedding: EmbeddingId,
                              keys: Iterable[str],
                              data: Iterable[RichData],
                              task_id: Optional[TaskId] = None) -> None:
    if isinstance(embedding, str):
      embed_fn = get_embedding_cls(embedding)()
    else:
      embed_fn = embedding

    embedding_name = embed_fn.name

    path = normalize_path(column)

    index_filename = embedding_index_filename(path, embedding_name)
    index_path = os.path.join(self.dataset_path, index_filename)

    index_info_filename = embedding_index_info_filename(path, embedding_name)
    index_info_path = os.path.join(self.dataset_path, index_info_filename)

    if file_exists(index_path):
      # The embedding index has already been computed.
      return

    # Write the embedding index and the ordered UUID column to disk so they can be joined later.
    if isinstance(keys, pd.Series):
      np_keys = keys.to_numpy()
    else:
      np_keys = np.array(keys)

    batches = chunks(data, size=embed_fn.batch_size)

    def _compute_embeddings(batches: Iterable[list[RichData]]) -> Iterable[np.ndarray]:
      for batch in batches:
        yield embed_fn(batch)

    batched_embeddings = progress(_compute_embeddings(batches),
                                  task_id=task_id,
                                  estimated_len=math.ceil(len(np_keys) / embed_fn.batch_size))
    embeddings = np.concatenate(list(batched_embeddings))

    with open_file(index_path, 'wb') as f:
      np.savez(f, **{NP_INDEX_KEYS_KWD: np_keys, NP_EMBEDDINGS_KWD: embeddings})

    # Write the index info.
    index_info = EmbeddingIndexInfo(column=path, embedding=embed_fn)
    with open_file(index_info_path, 'w') as f:
      f.write(index_info.json())


def embedding_index_filename(column: PathTuple, embedding_name: str) -> str:
  """Return the filename for the embedding index."""
  return f'{path_to_alias(column)}.{embedding_name}.embedding_index.npy'


EMBEDDING_INDEX_INFO_SUFFIX = 'embedding_index_info.json'


def embedding_index_info_filename(column: PathTuple, embedding_name: str) -> str:
  """Return the filename for the embedding index info."""
  return f'{path_to_alias(column)}.{embedding_name}.{EMBEDDING_INDEX_INFO_SUFFIX}'
