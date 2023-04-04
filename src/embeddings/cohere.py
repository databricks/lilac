"""Cohere embeddings."""
import functools
import os
from typing import Iterable

import cohere
import numpy as np
from sklearn.preprocessing import normalize
from tqdm import tqdm

from ..schema import RichData
from ..utils import chunks
from .embedding_registry import register_embed_fn

# Cohere only accepts 96 inputs at a time.
COHERE_EXAMPLE_LIMIT = 96


@functools.cache
def _co() -> cohere.Client:
  return cohere.Client(os.environ['COHERE_API_KEY'])


@register_embed_fn('cohere')
def embed(examples: Iterable[RichData]) -> np.ndarray:
  """Embed the examples using cohere."""
  embeddings = np.concatenate([
      np.array(_co().embed(chunk, truncate='START').embeddings)
      for chunk in tqdm(list(chunks(examples, size=COHERE_EXAMPLE_LIMIT)))
  ])

  return normalize(embeddings).astype(np.float16)
