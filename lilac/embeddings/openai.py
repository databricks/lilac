"""OpenAI embeddings."""
from typing import TYPE_CHECKING, Any, ClassVar, Iterable, cast

import numpy as np
from tenacity import retry, stop_after_attempt, wait_random_exponential
from typing_extensions import override

from ..env import env
from ..schema import Item, RichData
from ..signal import TextEmbeddingSignal
from ..splitters.spacy_splitter import clustering_spacy_chunker
from .embedding import compute_split_embeddings

if TYPE_CHECKING:
  import openai

API_NUM_PARALLEL_REQUESTS = 10
API_OPENAI_BATCH_SIZE = 128
API_EMBEDDING_MODEL = 'text-embedding-ada-002'
AZURE_NUM_PARALLEL_REQUESTS = 1
AZURE_OPENAI_BATCH_SIZE = 16


class OpenAI(TextEmbeddingSignal):
  """Computes embeddings using OpenAI's embedding API.

  <br>**Important**: This will send data to an external server!

  <br>To use this signal, you must get an OpenAI API key from
  [platform.openai.com](https://platform.openai.com/) and add it to your .env.local.

  <br>For details on pricing, see: https://openai.com/pricing.
  """

  name: ClassVar[str] = 'openai'
  display_name: ClassVar[str] = 'OpenAI Embeddings'

  _model: type['openai.Embedding']

  @override
  def setup(self) -> None:
    api_key = env('OPENAI_API_KEY')
    api_type = env('OPENAI_API_TYPE')
    api_base = env('OPENAI_API_BASE')
    api_version = env('OPENAI_API_VERSION')
    api_engine = env('OPENAI_API_ENGINE_EMBEDDING')
    if not api_key:
      raise ValueError('`OPENAI_API_KEY` environment variable not set.')
    try:
      import openai

    except ImportError:
      raise ImportError(
        'Could not import the "openai" python package. '
        'Please install it with `pip install openai`.'
      )
    else:
      openai.api_key = api_key
      self._api_engine = api_engine

      if api_type:
        openai.api_type = api_type
        openai.api_base = api_base
        openai.api_version = api_version

    try:
      openai.Model.list()
    except openai.error.AuthenticationError:
      raise openai.error.AuthenticationError(
        'Your `OPENAI_API_KEY` environment variable need to be completed with '
        '`OPENAI_API_TYPE`, `OPENAI_API_BASE`, `OPENAI_API_VERSION`, `OPENAI_API_ENGINE_EMBEDDING`'
      )
    else:
      self._model = openai.Embedding

  @override
  def compute(self, docs: Iterable[RichData]) -> Iterable[Item]:
    """Compute embeddings for the given documents."""

    @retry(wait=wait_random_exponential(min=1, max=20), stop=stop_after_attempt(10))
    def embed_fn(texts: list[str]) -> list[np.ndarray]:
      # Replace newlines, which can negatively affect performance.
      # See https://github.com/search?q=repo%3Aopenai%2Fopenai-python+replace+newlines&type=code
      texts = [text.replace('\n', ' ') for text in texts]

      response: Any = self._model.create(
        input=texts, model=API_EMBEDDING_MODEL, engine=self._api_engine
      )
      return [np.array(embedding['embedding'], dtype=np.float32) for embedding in response['data']]

    docs = cast(Iterable[str], docs)
    split_fn = clustering_spacy_chunker if self._split else None
    yield from compute_split_embeddings(
      docs,
      AZURE_OPENAI_BATCH_SIZE if self._api_engine else API_OPENAI_BATCH_SIZE,
      embed_fn,
      split_fn,
      num_parallel_requests=(
        AZURE_NUM_PARALLEL_REQUESTS if self._api_engine else API_NUM_PARALLEL_REQUESTS
      ),
    )
