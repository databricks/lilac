"""Utils for transformer embeddings."""

from typing import TYPE_CHECKING, Optional, Union

from ..utils import log

if TYPE_CHECKING:
  from sentence_transformers import SentenceTransformer
  from transformers import AutoModel

# This is not the literal pytorch batch dimension, but rather the batch of sentences passed to the
# model.encode function. The model will split this batch into smaller batches after sorting by text
# length (for performance reasons). A larger batch size gives sentence_transformer more
# opportunities to minimize padding by grouping similar sentence lengths together.
SENTENCE_TRANSFORMER_BATCH_SIZE = 1024


def prepare_model(
  model: Union['SentenceTransformer', 'AutoModel']
) -> Union['SentenceTransformer', 'AutoModel']:
  """Get a transformer model and the optimal batch size for it."""
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
    log(f'The model is using device: {preferred_device}')

  return model
