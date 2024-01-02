"""Jina embeddings hosted on Lilac's Garden."""
import gc
import gzip
import json
from io import BytesIO
from typing import ClassVar

import modal
import numpy as np
from numpy.linalg import norm
from typing_extensions import override

from lilac.utils import DebugTimer

from ..embeddings.embedding import chunked_compute_embedding
from ..schema import Item
from ..signal import TextEmbeddingSignal
from ..tasks import TaskExecutionType

# See readme in https://huggingface.co/jinaai/jina-embeddings-v2-small-en
_SIZE_TO_MODEL: dict[str, str] = {
  'small': 'jina-embeddings-v2-small-en',
  'base': 'jina-embeddings-v2-base-en',
}

# Anything larger than 1 slows down the computation because a single long document will cause
# padding to be added to all other documents in the batch.
JINA_BATCH_SIZE = 512
JINA_CONTEXT_SIZE = 8192
_NUM_THREADS = 10


class JinaV2Small(TextEmbeddingSignal):
  """Jina V2 Embeddings with 8K context.

  Each document is truncated to 8K characters, and the embeddings are computed on the truncated
  document.
  """

  name: ClassVar[str] = 'jina-v2-small'
  display_name: ClassVar[str] = 'Jina V2 (small)'
  map_batch_size: int = JINA_BATCH_SIZE
  map_parallelism: int = _NUM_THREADS
  map_strategy: TaskExecutionType = 'threads'

  _size = 'small'

  @override
  def setup(self) -> None:
    self._model = modal.Function.lookup('jina', 'Jina.embed')

  @override
  def teardown(self) -> None:
    del self._model
    gc.collect()

    try:
      import torch

      torch.cuda.empty_cache()
    except ImportError:
      pass

  @override
  def compute(self, docs: list[str]) -> list[Item]:
    """Call the embedding function."""

    # SentenceTransformers can take arbitrarily large batches.
    def _embed_fn(docs: list[str]) -> list[np.ndarray]:
      trimmed_docs = [doc[:JINA_CONTEXT_SIZE] for doc in docs]

      with DebugTimer(f'gzipping {len(docs)} docs'):
        buffer = BytesIO()
        # Gzip compress the data and write it to the buffer
        with gzip.GzipFile(fileobj=buffer, mode='w') as f:
          f.write(json.dumps(trimmed_docs).encode('utf-8'))
        gzipped_docs = buffer.getvalue()

      request = {'gzipped_docs': gzipped_docs}
      response = self._model.remote(request)
      vectors: list[list[float]] = response['vectors']
      embeddings: list[np.ndarray] = []
      for vector in vectors:
        vector_np = np.array(vector)
        vector_np /= norm(vector_np)
        embeddings.append(vector_np)
      return embeddings

    return chunked_compute_embedding(
      _embed_fn,
      docs,
      1_000_000_000,
    )


class JinaV2Base(JinaV2Small):
  """Jina V2 Embeddings with 8K context.

  Each document is truncated to 8K characters, and the embeddings are computed on the truncated
  document.
  """

  name: ClassVar[str] = 'jina-v2-base'
  display_name: ClassVar[str] = 'Jina V2 (base)'

  _size = 'base'
