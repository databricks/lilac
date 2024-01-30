"""Utils for transformer embeddings."""

import os
from typing import TYPE_CHECKING, Optional, Union

from ..utils import log

if TYPE_CHECKING:
  from sentence_transformers import SentenceTransformer
  from transformers import AutoModel

# This is not the literal pytorch batch dimension, but rather the batch of sentences passed to the
# model.encode function. The model will split this batch into smaller batches after sorting by text
# length (for performance reasons). A larger batch size gives sentence_transformer more
# opportunities to minimize padding by grouping similar sentence lengths together.
SENTENCE_TRANSFORMER_BATCH_SIZE = 256

# We're using joblib, which uses spawning, not forking. So it should be safe to hardcode this to
# true without deadlocks.
os.environ['TOKENIZERS_PARALLELISM'] = 'true'


def setup_model_device(
  model: Union['SentenceTransformer', 'AutoModel'],
  model_name: str,
) -> Union['SentenceTransformer', 'AutoModel']:
  """Prepare a transformer model to run on the most efficient device / backend."""
  try:
    import torch.backends.mps
  except ImportError:
    raise ImportError(
      'Could not import the "torch" python package. ' 'Please install it with `pip install "torch".'
    )
  preferred_device: Optional[str] = None
  if torch.backends.mps.is_available():
    preferred_device = 'mps'
  elif torch.cuda.is_available():
    preferred_device = 'cuda'
  elif not torch.backends.mps.is_built():
    log('MPS not available because the current PyTorch install was not built with MPS enabled.')

  if preferred_device:
    model = model.to(preferred_device)

  log(f'{model_name} using device: {model.device}')

  return model
