"""OpenAI embeddings."""
from typing import ClassVar, Optional

import numpy as np
from tenacity import retry, stop_after_attempt, wait_random_exponential
from typing_extensions import override

from ..env import env
from ..schema import Item
from ..signal import TextEmbeddingSignal
from ..splitters.spacy_splitter import clustering_spacy_chunker
from ..tasks import TaskExecutionType
from .embedding import chunked_compute_embedding

API_NUM_PARALLEL_REQUESTS = 10
API_OPENAI_BATCH_SIZE = 128
API_EMBEDDING_MODEL = 'text-embedding-ada-002'
AZURE_NUM_PARALLEL_REQUESTS = 1
AZURE_OPENAI_BATCH_SIZE = 16


class OpenAIEmbedding(TextEmbeddingSignal):
  """Computes embeddings using OpenAI's embedding API.

  <br>**Important**: This will send data to an external server!

  <br>To use this signal, you must get an OpenAI API key from
  [platform.openai.com](https://platform.openai.com/) and add it to your .env.local.

  <br>For details on pricing, see: https://openai.com/pricing.
  """

  name: ClassVar[str] = 'openai'
  display_name: ClassVar[str] = 'OpenAI Embeddings'
  local_batch_size: ClassVar[int] = API_OPENAI_BATCH_SIZE
  local_parallelism: ClassVar[int] = API_NUM_PARALLEL_REQUESTS
  local_strategy: ClassVar[TaskExecutionType] = 'threads'

  @override
  def setup(self) -> None:
    api_key = env('OPENAI_API_KEY')
    api_base = env('OPENAI_API_BASE')
    azure_api_key = env('AZURE_OPENAI_KEY')
    azure_api_version = env('AZURE_OPENAI_VERSION')
    azure_api_endpoint = env('AZURE_OPENAI_ENDPOINT')

    if not api_key and not azure_api_key:
      raise ValueError(
        '`OPENAI_API_KEY` or `AZURE_OPENAI_KEY` ' 'environment variables not set, please set one.'
      )
    if api_key and azure_api_key:
      raise ValueError(
        'Both `OPENAI_API_KEY` and `AZURE_OPENAI_KEY` '
        'environment variables are set, please set only one.'
      )

    try:
      import openai

    except ImportError:
      raise ImportError(
        'Could not import the "openai" python package. '
        'Please install it with `pip install openai`.'
      )

    else:
      if api_key:
        self._client = openai.OpenAI(api_key=api_key, base_url=api_base)
        self._azure = False

      elif azure_api_key:
        self._client = openai.AzureOpenAI(
          api_key=azure_api_key, api_version=azure_api_version, azure_endpoint=azure_api_endpoint
        )
        self._azure = True
        OpenAIEmbedding.local_batch_size = AZURE_OPENAI_BATCH_SIZE
        OpenAIEmbedding.local_parallelism = AZURE_NUM_PARALLEL_REQUESTS

  @override
  def compute(self, docs: list[str]) -> list[Optional[Item]]:
    """Compute embeddings for the given documents."""

    @retry(wait=wait_random_exponential(min=1, max=20), stop=stop_after_attempt(10))
    def embed_fn(texts: list[str]) -> list[np.ndarray]:
      # Replace newlines, which can negatively affect performance.
      # See https://github.com/search?q=repo%3Aopenai%2Fopenai-python+replace+newlines&type=code
      texts = [text.replace('\n', ' ') for text in texts]

      response = self._client.embeddings.create(
        input=texts,
        model=API_EMBEDDING_MODEL if not self._azure else env('AZURE_OPENAI_EMBEDDING_MODEL'),
      )
      return [np.array(embedding.embedding, dtype=np.float32) for embedding in response.data]

    return chunked_compute_embedding(
      embed_fn, docs, self.local_batch_size, chunker=clustering_spacy_chunker
    )
