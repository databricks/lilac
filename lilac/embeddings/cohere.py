"""Cohere embeddings."""
from typing import TYPE_CHECKING, Iterable, cast

import numpy as np
from typing_extensions import override

from ..env import env
from ..schema import Item, RichData
from ..signal import TextEmbeddingSignal
from ..splitters.chunk_splitter import split_text
from .embedding import compute_split_embeddings

if TYPE_CHECKING:
  from cohere import Client

NUM_PARALLEL_REQUESTS = 10
COHERE_BATCH_SIZE = 96


class Cohere(TextEmbeddingSignal):
  """Computes embeddings using Cohere's embedding API.

  <br>**Important**: This will send data to an external server!

  <br>To use this signal, you must get a Cohere API key from
  [cohere.com/embed](https://cohere.com/embed) and add it to your .env.local.

  <br>For details on pricing, see: https://cohere.com/pricing.
  """

  name = 'cohere'
  display_name = 'Cohere Embeddings'

  _model: 'Client'

  @override
  def setup(self) -> None:
    """Validate that the api key and python package exists in environment."""
    api_key = env('COHERE_API_KEY')
    if not api_key:
      raise ValueError('`COHERE_API_KEY` environment variable not set.')
    try:
      import cohere
      self._model = cohere.Client(api_key, max_retries=10)
    except ImportError:
      raise ImportError('Could not import the "cohere" python package. '
                        'Please install it with `pip install cohere`.')

  @override
  def compute(self, docs: Iterable[RichData]) -> Iterable[Item]:
    """Compute embeddings for the given documents."""

    def embed_fn(texts: list[str]) -> list[np.ndarray]:
      return self._model.embed(texts, truncate='END').embeddings

    docs = cast(Iterable[str], docs)
    split_fn = split_text if self._split else None
    yield from compute_split_embeddings(
      docs, COHERE_BATCH_SIZE, embed_fn, split_fn, num_parallel_requests=NUM_PARALLEL_REQUESTS)
