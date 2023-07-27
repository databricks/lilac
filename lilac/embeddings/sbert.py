"""Sentence-BERT embeddings. Open-source models, designed to run on device."""
import functools
import os
from typing import TYPE_CHECKING, Iterable, Optional, cast

from typing_extensions import override

from ..config import data_path
from ..schema import Item, RichData
from ..signals.signal import TextEmbeddingSignal
from ..signals.splitters.chunk_splitter import split_text
from ..utils import log
from .embedding import compute_split_embeddings

if TYPE_CHECKING:
  from sentence_transformers import SentenceTransformer

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
def _sbert() -> tuple[Optional[str], 'SentenceTransformer']:
  try:
    import torch.backends.mps
    from sentence_transformers import SentenceTransformer
  except ImportError:
    raise ImportError('Could not import the "sentence_transformers" python package. '
                      'Please install it with `pip install sentence-transformers`.')
  preferred_device: Optional[str] = None
  if torch.backends.mps.is_available():
    preferred_device = 'mps'
  elif not torch.backends.mps.is_built():
    log('MPS not available because the current PyTorch install was not built with MPS enabled.')
  return preferred_device, SentenceTransformer(
    MODEL_NAME, device=preferred_device, cache_folder=os.path.join(data_path(), '.cache'))


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

    embed_fn = model.encode
    split_fn = split_text if self._split else None
    docs = cast(Iterable[str], docs)
    yield from compute_split_embeddings(docs, batch_size, embed_fn=embed_fn, split_fn=split_fn)
