"""Utils for transformer embeddings."""

import functools
import os
from typing import TYPE_CHECKING, Optional

from ..env import data_path
from ..utils import log

if TYPE_CHECKING:
  from sentence_transformers import SentenceTransformer


def get_model(model_name: str,
              optimal_batch_sizes: dict[str, int] = {}) -> tuple[int, 'SentenceTransformer']:
  """Get a transformer model and the optimal batch size for it."""
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

  @functools.cache
  def _get_model(model_name: str) -> 'SentenceTransformer':
    return SentenceTransformer(
      model_name, device=preferred_device, cache_folder=os.path.join(data_path(), '.cache'))

  batch_size = optimal_batch_sizes[preferred_device or '']
  return batch_size, _get_model(model_name)
