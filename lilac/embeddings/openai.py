"""OpenAI embeddings."""
from typing import TYPE_CHECKING, Any, Iterable, cast

import numpy as np
from tenacity import retry, stop_after_attempt, wait_random_exponential
from typing_extensions import override

from ..env import env
from ..schema import Item, RichData
from ..signal import TextEmbeddingSignal
from ..splitters.chunk_splitter import split_text
from .embedding import compute_split_embeddings

if TYPE_CHECKING:
  import openai

NUM_PARALLEL_REQUESTS = 10
OPENAI_BATCH_SIZE = 128
EMBEDDING_MODEL = 'text-embedding-ada-002'


class OpenAI(TextEmbeddingSignal):
  """Computes embeddings using OpenAI's embedding API.

  <br>**Important**: This will send data to an external server!

  <br>To use this signal, you must get an OpenAI API key from
  [platform.openai.com](https://platform.openai.com/) and add it to your .env.local.

  <br>For details on pricing, see: https://openai.com/pricing.
  """

  name = 'openai'
  display_name = 'OpenAI Embeddings'

  _model: type['openai.Embedding']

  @override
  def setup(self) -> None:
    api_key = env('OPENAI_API_KEY')
    if not api_key:
      raise ValueError('`OPENAI_API_KEY` environment variable not set.')
    try:
      import openai
      openai.api_key = api_key
      self._model = openai.Embedding
    except ImportError:
      raise ImportError('Could not import the "openai" python package. '
                        'Please install it with `pip install openai`.')

  @override
  def compute(self, docs: Iterable[RichData]) -> Iterable[Item]:
    """Compute embeddings for the given documents."""

    @retry(wait=wait_random_exponential(min=1, max=20), stop=stop_after_attempt(10))
    def embed_fn(texts: list[str]) -> list[np.ndarray]:

      # Replace newlines, which can negatively affect performance.
      # See https://github.com/search?q=repo%3Aopenai%2Fopenai-python+replace+newlines&type=code
      texts = [text.replace('\n', ' ') for text in texts]

      response: Any = self._model.create(input=texts, model=EMBEDDING_MODEL)
      return [np.array(embedding['embedding'], dtype=np.float32) for embedding in response['data']]

    docs = cast(Iterable[str], docs)
    split_fn = split_text if self._split else None
    yield from compute_split_embeddings(
      docs, OPENAI_BATCH_SIZE, embed_fn, split_fn, num_parallel_requests=NUM_PARALLEL_REQUESTS)
