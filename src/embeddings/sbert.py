"""Sentence-BERT embeddings. Open-source models, designed to run on device."""
from typing import Any, Iterable, Optional, cast

import torch
from sentence_transformers import SentenceTransformer
from typing_extensions import override

from ..schema import Item, RichData
from ..signals.signal import TextEmbeddingSignal
from ..signals.splitters.chunk_splitter import TextChunk, split_text
from ..utils import log
from .embedding import split_and_combine_text_embeddings

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
  def compute(self, docs: Iterable[RichData]) -> Iterable[Item]:
    """Call the embedding function."""
    batch_size = self._optimal_batch_size()

    def splitter(doc: str) -> list[TextChunk]:
      if self._split:
        return split_text(doc, chunk_overlap=0)
      else:
        # Return a single chunk that spans the entire document.
        return [(doc, (0, len(doc)))]

    docs = cast(Iterable[str], docs)
    yield from split_and_combine_text_embeddings(docs, batch_size, splitter, self._model.encode)
