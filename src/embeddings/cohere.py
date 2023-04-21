"""Cohere embeddings."""
import functools
import os
from typing import Iterable

import cohere
import numpy as np
from sklearn.preprocessing import normalize
from typing_extensions import override

from ..schema import EnrichmentType, RichData
from .embedding_registry import Embedding


@functools.cache
def _cohere() -> cohere.Client:
  api_key = os.environ.get('COHERE_API_KEY', None)
  if not api_key:
    raise ValueError('`COHERE_API_KEY` environment variable not set.')
  return cohere.Client(api_key)


class Cohere(Embedding):
  """Cohere embedding."""
  name = 'cohere'
  enrichment_type = EnrichmentType.TEXT
  # Cohere only accepts 96 inputs at a time.
  batch_size = 96

  @override
  def __call__(self, data: Iterable[RichData]) -> np.ndarray:
    """Call the embedding function."""
    return normalize(np.array(_cohere().embed(list(data),
                                              truncate='START').embeddings)).astype(np.float16)
