"""An embedding indexer that stores the embedding index on disk."""
import os
import pathlib
from typing import Iterable, Optional, Union

import numpy as np
import pandas as pd
from typing_extensions import override

from ..schema import Path, RichData, path_to_alias
from ..utils import file_exists, open_file
from .embedding_index import EmbeddingIndex, EmbeddingIndexer
from .embedding_registry import EmbeddingId, get_embed_fn

NP_INDEX_KEYS_KWD = 'keys'
NP_EMBEDDINGS_KWD = 'embeddings'


class EmbeddingIndexerDisk(EmbeddingIndexer):
  """An embedding indexer that stores the embedding index on disk."""

  def __init__(self, dataset_path: Union[str, pathlib.Path]) -> None:
    self.dataset_path = dataset_path

  @override
  def get_embedding_index(self,
                          column: Path,
                          embedding: EmbeddingId,
                          keys: Optional[Iterable[bytes]] = None) -> EmbeddingIndex:
    embedding_name, _ = get_embed_fn(embedding)

    index_filename = embedding_index_filename(column, embedding_name)
    index_path = os.path.join(self.dataset_path, index_filename)

    if not file_exists(index_path):
      raise ValueError(
          F'Embedding index for column "{column}" and embedding "{embedding_name}" does not exist. '
          'Please run "db.compute_embedding_index" on the database first.')

    keys_ndarray: Optional[np.ndarray] = None
    if keys is not None:
      keys_ndarray = np.array(keys, dtype=bytes)

    # Read the embedding index from disk.
    with open_file(index_path, 'rb') as f:
      np_index: dict[str, np.ndarray] = np.load(f)
      if keys_ndarray is not None:
        # NOTE: Calling tolist() here is necessary because we can't put the entire matrix into the
        # dataframe. This will store each embedding a list. This could be sped up if we write our
        # own implementation, or use something faster.
        df = pd.DataFrame({NP_EMBEDDINGS_KWD: np_index[NP_EMBEDDINGS_KWD].tolist()},
                          index=np_index[NP_INDEX_KEYS_KWD])
        embeddings = np.stack(df.loc[keys_ndarray][NP_EMBEDDINGS_KWD])
      else:
        embeddings = np_index[NP_EMBEDDINGS_KWD]

    return EmbeddingIndex(path=index_path, embeddings=embeddings)

  @override
  def compute_embedding_index(self, column: Path, embedding: EmbeddingId, keys: Iterable[bytes],
                              data: Iterable[RichData]) -> None:
    embedding_name, embed_fn = get_embed_fn(embedding)

    index_filename = embedding_index_filename(column, embedding_name)
    index_path = os.path.join(self.dataset_path, index_filename)

    if file_exists(index_path):
      # The embedding index has already been computed.
      return

    embeddings = embed_fn(data)
    # Write the embedding index and the ordered UUID column to disk so they can be joined later.
    with open_file(index_path, 'wb') as f:
      np.savez(f, **{NP_INDEX_KEYS_KWD: np.array(keys, dtype=bytes), NP_EMBEDDINGS_KWD: embeddings})


def embedding_index_filename(column: Path, embedding_name: str) -> str:
  """Return the filename for the embedding index."""
  return f'{path_to_alias(column)}.{embedding_name}.embedding_index.npy'
