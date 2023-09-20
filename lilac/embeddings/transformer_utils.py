"""Utils for transformer embeddings."""

import functools
from typing import TYPE_CHECKING, Optional

from ..utils import log

if TYPE_CHECKING:
  from sentence_transformers import SentenceTransformer


@functools.cache
def _get_model(model_name: str, preferred_device: Optional[str]) -> 'SentenceTransformer':
  try:
    from sentence_transformers import SentenceTransformer
  except ImportError:
    raise ImportError('Could not import the "sentence_transformers" python package. '
                      'Please install it with `pip install "lilac[gte]".')
  return SentenceTransformer(model_name, device=preferred_device)


def get_model(model_name: str,
              optimal_batch_sizes: dict[str, int] = {}) -> tuple[int, 'SentenceTransformer']:
  """Get a transformer model and the optimal batch size for it."""
  try:
    import torch.backends.mps
  except ImportError:
    raise ImportError('Could not import the "sentence_transformers" python package. '
                      'Please install it with `pip install "lilac[gte]".')
  preferred_device: Optional[str] = None
  if torch.backends.mps.is_available():
    preferred_device = 'mps'
  elif not torch.backends.mps.is_built():
    log('MPS not available because the current PyTorch install was not built with MPS enabled.')

  batch_size = optimal_batch_sizes[preferred_device or '']
  return batch_size, _get_model(model_name, preferred_device)
