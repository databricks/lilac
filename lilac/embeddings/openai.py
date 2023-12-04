"""OpenAI embeddings."""
from typing import Any, ClassVar, Iterable, cast

import numpy as np
from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_random_exponential
from typing_extensions import override

from ..env import env
from ..schema import Item, RichData
from ..signal import TextEmbeddingSignal
from ..splitters.spacy_splitter import clustering_spacy_chunker
from .embedding import compute_split_embeddings

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

  @override
  def setup(self) -> None:
    api_key = env('OPENAI_API_KEY')
    api_type = env('OPENAI_API_TYPE')
    api_version = env('OPENAI_API_VERSION')
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

      if api_type:
        openai.api_type = api_type
        openai.api_version = api_version

    try:
      openai.models.list()
    except openai.AuthenticationError:
      raise ValueError(
        'Your `OPENAI_API_KEY` environment variable need to be completed with '
        '`OPENAI_API_TYPE`, `OPENAI_API_VERSION`, `OPENAI_API_ENGINE_EMBEDDING`'
      )

  @override
  def compute(self, docs: Iterable[RichData]) -> Iterable[Item]:
    """Compute embeddings for the given documents."""
    client = OpenAI()

    @retry(wait=wait_random_exponential(min=1, max=20), stop=stop_after_attempt(10))
    def embed_fn(texts: list[str]) -> list[np.ndarray]:
      # Replace newlines, which can negatively affect performance.
      # See https://github.com/search?q=repo%3Aopenai%2Fopenai-python+replace+newlines&type=code
      texts = [text.replace('\n', ' ') for text in texts]

      response: Any = client.embeddings.create(
        input=texts,
        model=API_EMBEDDING_MODEL,
      )
      return [np.array(embedding['embedding'], dtype=np.float32) for embedding in response['data']]

    docs = cast(Iterable[str], docs)
    split_fn = clustering_spacy_chunker if self._split else None
    yield from compute_split_embeddings(
      docs,
      AZURE_OPENAI_BATCH_SIZE,
      embed_fn,
      split_fn,
      num_parallel_requests=(AZURE_NUM_PARALLEL_REQUESTS),
    )
