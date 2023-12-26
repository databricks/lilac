"""Jina embeddings. Open-source, designed to run on device, with 8K context."""
import gc
from typing import TYPE_CHECKING, ClassVar, Iterable, Iterator, cast

from ..utils import chunks
from .transformer_utils import setup_model_device

if TYPE_CHECKING:
  from transformers import AutoModel

import numpy as np
from numpy.linalg import norm
from typing_extensions import override

from ..schema import Item, RichData, lilac_embedding
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

  _size = 'small'
  _model: 'AutoModel'

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
    self._model.cpu()
    del self._model
    gc.collect()

    try:
      import torch

      torch.cuda.empty_cache()
    except ImportError:
      pass

  @override
  def compute(self, docs: Iterable[RichData]) -> Iterator[Item]:
    docs = cast(Iterable[str], docs)

    for batch_docs in chunks(docs, JINA_BATCH_SIZE):
      trimmed_docs = [doc[:JINA_CONTEXT_SIZE] for doc in batch_docs]
      vectors = self._model.encode(trimmed_docs)
      for doc, vector in zip(trimmed_docs, vectors):
        vector = np.array(vector)
        vector /= norm(vector)
        yield [lilac_embedding(0, len(doc), vector)]


class JinaV2Base(JinaV2Small):
  """Jina V2 Embeddings with 8K context.

  Each document is truncated to 8K characters, and the embeddings are computed on the truncated
  document.
  """

  name: ClassVar[str] = 'jina-v2-base'
  display_name: ClassVar[str] = 'Jina V2 (base)'

  _size = 'base'
