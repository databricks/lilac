"""Jina embeddings. Open-source, designed to run on device, with 8K context."""
import gc
from typing import TYPE_CHECKING, Any, ClassVar, Optional, cast

from ..embeddings.embedding import chunked_compute_embedding
from ..tasks import TaskExecutionType
from .transformer_utils import setup_model_device

if TYPE_CHECKING:
  from transformers import AutoModel

import numpy as np
from numpy.linalg import norm
from typing_extensions import override

from ..schema import Item
from ..signal import TextEmbeddingSignal

# See readme in https://huggingface.co/jinaai/jina-embeddings-v2-small-en
_SIZE_TO_MODEL: dict[str, str] = {
  'small': 'jina-embeddings-v2-small-en',
  'base': 'jina-embeddings-v2-base-en',
}

# Anything larger than 1 slows down the computation because a single long document will cause
# padding to be added to all other documents in the batch.
JINA_BATCH_SIZE = 1
JINA_CONTEXT_SIZE = 8192


class JinaV2Small(TextEmbeddingSignal):
  """Jina V2 Embeddings with 8K context.

  Each document is truncated to 8K characters, and the embeddings are computed on the truncated
  document.
  """

  name: ClassVar[str] = 'jina-v2-small'
  display_name: ClassVar[str] = 'Jina V2 (small)'
  map_batch_size: ClassVar[int] = JINA_BATCH_SIZE
  map_parallelism: ClassVar[int] = 1
  map_strategy: ClassVar[TaskExecutionType] = 'threads'

  _size = 'small'
  _model: Optional['AutoModel'] = None

  @override
  def setup(self) -> None:
    try:
      from transformers import AutoModel
    except ImportError:
      raise ImportError(
        'Could not import the `transformers` python package. '
        'Please install it with `pip install transformers`.'
      )
    # trust_remote_code is needed to use the encode method.
    model_name = f'jinaai/{_SIZE_TO_MODEL[self._size]}'
    self._model = setup_model_device(
      AutoModel.from_pretrained(model_name, trust_remote_code=True), model_name
    )

  @override
  def teardown(self) -> None:
    if self._model is None:
      return
    self._model.cpu()
    del self._model
    try:
      import torch

      torch.cuda.empty_cache()
    except ImportError:
      pass
    gc.collect()

  @override
  def compute(self, docs: list[str]) -> list[Item]:
    """Call the embedding function."""
    if self._model is None:
      raise ValueError('The signal is not initialized. Call setup() first.')

    # SentenceTransformers can take arbitrarily large batches.
    def _embed_fn(docs: list[str]) -> list[np.ndarray]:
      trimmed_docs = [doc[:JINA_CONTEXT_SIZE] for doc in docs]
      vectors = cast(Any, self._model).encode(trimmed_docs)
      embeddings = []
      for vector in vectors:
        vector = np.array(vector)
        vector /= norm(vector)
        embeddings.append(vector)
      return embeddings

    return chunked_compute_embedding(
      _embed_fn,
      docs,
      self.map_batch_size,
    )


class JinaV2Base(JinaV2Small):
  """Jina V2 Embeddings with 8K context.

  Each document is truncated to 8K characters, and the embeddings are computed on the truncated
  document.
  """

  name: ClassVar[str] = 'jina-v2-base'
  display_name: ClassVar[str] = 'Jina V2 (base)'

  _size = 'base'
