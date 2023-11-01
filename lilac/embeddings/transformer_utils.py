"""Utils for transformer embeddings."""

import functools
from typing import TYPE_CHECKING, Optional

from ..utils import log

if TYPE_CHECKING:
  from sentence_transformers import SentenceTransformer

# This is not the literal pytorch batch dimension, but rather the batch of sentences passed to the
# model.encode function. The model will split this batch into smaller batches after sorting by text
# length (for performance reasons). A larger batch size gives sentence_transformer more
# opportunities to minimize padding by grouping similar sentence lengths together.
SENTENCE_TRANSFORMER_BATCH_SIZE = 1024


@functools.cache
def _get_model(model_name: str, preferred_device: Optional[str]) -> 'SentenceTransformer':
  try:
    from sentence_transformers import SentenceTransformer
  except ImportError:
    raise ImportError(
      'Could not import the "sentence_transformers" python package. '
      'Please install it with `pip install "lilac[gte]".'
    )
  return SentenceTransformer(model_name, device=preferred_device)


def get_model(model_name: str) -> 'SentenceTransformer':
  """Get a transformer model and the optimal batch size for it."""
  try:
    import torch.backends.mps
  except ImportError:
    raise ImportError(
      'Could not import the "sentence_transformers" python package. '
      'Please install it with `pip install "lilac[gte]".'
    )
  preferred_device: Optional[str] = None
  if torch.backends.mps.is_available():
    preferred_device = 'mps'
  elif not torch.backends.mps.is_built():
    log('MPS not available because the current PyTorch install was not built with MPS enabled.')

  return _get_model(model_name, preferred_device)
