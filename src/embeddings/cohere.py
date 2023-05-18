"""Cohere embeddings."""
import functools
from typing import Iterable

import cohere
import numpy as np
from sklearn.preprocessing import normalize
from typing_extensions import override

from ..config import CONFIG
from ..schema import RichData, SignalOut
from ..signals.signal import TextEmbeddingSignal
from ..utils import chunks

COHERE_BATCH_SIZE = 96


@functools.cache
def _cohere() -> cohere.Client:
  api_key = CONFIG['COHERE_API_KEY']
  if not api_key:
    raise ValueError('`COHERE_API_KEY` environment variable not set.')
  return cohere.Client(api_key)


class Cohere(TextEmbeddingSignal):
  """Computes embeddings using Cohere's embedding API.

  <br>**Important**: This will send data to an external server!

  <br>To use this signal, you must get a Cohere API key from
  [cohere.com/embed](https://cohere.com/embed) and add it to your .env.local.

  <br>For details on pricing, see: https://cohere.com/pricing.
  """

  name = 'cohere'
  display_name = 'Cohere Embeddings'

  @override
  def compute(self, data: Iterable[RichData]) -> Iterable[SignalOut]:
    """Call the embedding function."""
    batches = chunks(data, COHERE_BATCH_SIZE)
    for batch in batches:
      embedding_batch = normalize(np.array(_cohere().embed(
        batch, truncate='END').embeddings)).astype(np.float16)
      # np.split returns a shallow copy of each embedding so we don't increase the memory footprint.
      yield from np.split(embedding_batch, embedding_batch.shape[0])
