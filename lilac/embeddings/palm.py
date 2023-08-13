"""PaLM embeddings."""
from typing import TYPE_CHECKING, Iterable, cast

import numpy as np
from tenacity import retry, stop_after_attempt, wait_random_exponential
from typing_extensions import override

from ..env import env
from ..schema import Item, RichData
from ..signal import TextEmbeddingSignal
from ..splitters.chunk_splitter import split_text
from .embedding import compute_split_embeddings

if TYPE_CHECKING:
  import google.generativeai as palm

PALM_BATCH_SIZE = 1  # PaLM API only supports batch size 1.
NUM_PARALLEL_REQUESTS = 256  # Because batch size is 1, we can send many requests in parallel.
EMBEDDING_MODEL = 'models/embedding-gecko-001'


class PaLM(TextEmbeddingSignal):
  """Computes embeddings using PaLM's embedding API.

  <br>**Important**: This will send data to an external server!

  <br>To use this signal, you must get a PaLM API key from
  [makersuite.google.com](https://makersuite.google.com/app/apikey) and add it to your .env.local.
  """

  name = 'palm'
  display_name = 'PaLM Embeddings'

  _model: 'palm.generate_embeddings'

  @override
  def setup(self) -> None:
    api_key = env('PALM_API_KEY')
    if not api_key:
      raise ValueError('`PALM_API_KEY` environment variable not set.')
    try:
      import google.generativeai as palm
      palm.configure(api_key=api_key)
      self._model = palm.generate_embeddings
    except ImportError:
      raise ImportError('Could not import the "google.generativeai" python package. '
                        'Please install it with `pip install google-generativeai`.')

  @override
  def compute(self, docs: Iterable[RichData]) -> Iterable[Item]:
    """Compute embeddings for the given documents."""

    @retry(wait=wait_random_exponential(min=1, max=20), stop=stop_after_attempt(10))
    def embed_fn(texts: list[str]) -> list[np.ndarray]:
      assert len(texts) == 1, 'PaLM API only supports batch size 1.'
      response = self._model(model=EMBEDDING_MODEL, text=texts[0])
      return [np.array(response['embedding'], dtype=np.float32)]

    docs = cast(Iterable[str], docs)
    split_fn = split_text if self._split else None
    yield from compute_split_embeddings(
      docs, PALM_BATCH_SIZE, embed_fn, split_fn, num_parallel_requests=NUM_PARALLEL_REQUESTS)
