"""Sentence-BERT embeddings. Open-source models, designed to run on device."""
from typing import Any, Iterable, Optional

import numpy as np
import torch
from sentence_transformers import SentenceTransformer
from sklearn.preprocessing import normalize
from typing_extensions import override

from ..schema import Item, RichData
from ..signals.signal import TextEmbeddingSignal
from ..utils import chunks, log

# The `all-mpnet-base-v2` model provides the best quality, while `all-MiniLM-L6-v2`` is 5 times
# faster and still offers good quality. See https://www.sbert.net/docs/pretrained_models.html#sentence-embedding-models/
MINI_LM_MODEL = 'all-MiniLM-L6-v2'

SBERT_DEFAULT_BATCH_SIZE = 64
# Maps a tuple of model name and device to the optimal batch size, found empirically.
SBERT_OPTIMAL_BATCH_SIZE: dict[tuple[str, str], int] = {
  (MINI_LM_MODEL, 'mps'): 256,
}


class SBERT(TextEmbeddingSignal):
  """Computes embeddings using Sentence-BERT library."""

  name = 'sbert'
  display_name = 'SBERT Embeddings'
  model_name = MINI_LM_MODEL

  _model: SentenceTransformer
  _device: Optional[str] = None

  def __init__(self, **data: Any):
    super().__init__(**data)

    if torch.backends.mps.is_available():
      self._device = 'mps'
    elif not torch.backends.mps.is_built():
      log('MPS not available because the current PyTorch install was not built with MPS enabled.')
    self._model = SentenceTransformer(self.model_name, device=self._device)

  def _optimal_batch_size(self) -> int:
    model_device = (self.model_name, str(self._device))
    if model_device in SBERT_OPTIMAL_BATCH_SIZE:
      return SBERT_OPTIMAL_BATCH_SIZE[model_device]
    return SBERT_DEFAULT_BATCH_SIZE

  @override
  def compute(self, data: Iterable[RichData]) -> Iterable[Item]:
    batch_size = self._optimal_batch_size()

    for batch in chunks(data, batch_size):
      embedding_batch = np.array(self._model.encode(batch))
      embedding_batch = normalize(embedding_batch).astype(np.float16)
      # np.split returns a shallow copy of each embedding so we don't increase the memory footprint.
      yield from np.split(embedding_batch, embedding_batch.shape[0])
