"""Sentence-BERT embeddings. Open-source models, designed to run on device."""
import functools
from typing import Iterable, Optional, cast

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


@functools.cache
def _sbert() -> tuple[Optional[str], SentenceTransformer]:
  preferred_device: Optional[str] = None
  if torch.backends.mps.is_available():
    preferred_device = 'mps'
  elif not torch.backends.mps.is_built():
    log('MPS not available because the current PyTorch install was not built with MPS enabled.')
  return preferred_device, SentenceTransformer(MODEL_NAME, device=preferred_device)


def _optimal_batch_size(preferred_device: Optional[str]) -> int:
  model_device = (MODEL_NAME, str(preferred_device))
  if model_device in SBERT_OPTIMAL_BATCH_SIZE:
    return SBERT_OPTIMAL_BATCH_SIZE[model_device]
  return SBERT_DEFAULT_BATCH_SIZE


class SBERT(TextEmbeddingSignal):
  """Computes embeddings using Sentence-BERT library."""

  name = 'sbert'
  display_name = 'SBERT Embeddings'

  @override
  def compute(self, docs: Iterable[RichData]) -> Iterable[Item]:
    """Call the embedding function."""
    preferred_device, model = _sbert()
    batch_size = _optimal_batch_size(preferred_device)

    def splitter(doc: str) -> list[TextChunk]:
      if self._split:
        return split_text(doc, chunk_overlap=0)
      else:
        # Return a single chunk that spans the entire document.
        return [(doc, (0, len(doc)))]

    docs = cast(Iterable[str], docs)
    yield from split_and_combine_text_embeddings(docs, batch_size, splitter, model.encode)
