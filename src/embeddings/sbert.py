"""Sentence-BERT embeddings. Open-source models, designed to run on device."""
from typing import Any, Iterable, Optional, cast

import numpy as np
import torch
from sentence_transformers import SentenceTransformer
from sklearn.preprocessing import normalize
from typing_extensions import override

from ..data.dataset_utils import lilac_embedding
from ..schema import Item, RichData
from ..signals.signal import TextEmbeddingSignal
from ..signals.splitters.chunk_splitter import split_text
from ..utils import chunks, log

# The `all-mpnet-base-v2` model provides the best quality, while `all-MiniLM-L6-v2`` is 5 times
# faster and still offers good quality. See https://www.sbert.net/docs/pretrained_models.html#sentence-embedding-models/
MINI_LM_MODEL = 'all-MiniLM-L6-v2'

SBERT_DEFAULT_BATCH_SIZE = 64
# Maps a tuple of model name and device to the optimal batch size, found empirically.
SBERT_OPTIMAL_BATCH_SIZE: dict[tuple[str, str], int] = {
  (MINI_LM_MODEL, 'mps'): 256,
}

MODEL_NAME = MINI_LM_MODEL


class SBERT(TextEmbeddingSignal):
  """Computes embeddings using Sentence-BERT library."""

  name = 'sbert'
  display_name = 'SBERT Embeddings'

  _model: SentenceTransformer
  _device: Optional[str] = None

  def __init__(self, **data: Any):
    super().__init__(**data)

    if torch.backends.mps.is_available():
      self._device = 'mps'
    elif not torch.backends.mps.is_built():
      log('MPS not available because the current PyTorch install was not built with MPS enabled.')
    self._model = SentenceTransformer(MODEL_NAME, device=self._device)

  def _optimal_batch_size(self) -> int:
    model_device = (MODEL_NAME, str(self._device))
    if model_device in SBERT_OPTIMAL_BATCH_SIZE:
      return SBERT_OPTIMAL_BATCH_SIZE[model_device]
    return SBERT_DEFAULT_BATCH_SIZE

  @override
  def compute(self, data: Iterable[RichData]) -> Iterable[Item]:
    """Call the embedding function."""
    batch_size = self._optimal_batch_size()
    # We will yield several spans for each input text.
    for text in data:
      text = cast(str, text)
      text_chunks = split_text(text, chunk_overlap=0) if self._split else [(text, (0, len(text)))]
      all_embeddings: list[np.ndarray] = []
      for batch in chunks(text_chunks, batch_size):
        embedding_batch = normalize(np.array(self._model.encode(batch))).astype(np.float16)
        # np.split returns a shallow copy of each embedding so we don't increase the mem footprint.
        all_embeddings.extend(np.split(embedding_batch, embedding_batch.shape[0]))

      # Yield many spans for each input text.
      yield [
        lilac_embedding(start, end, embedding)
        for (_, (start, end)), embedding in zip(text_chunks, all_embeddings)
      ]
