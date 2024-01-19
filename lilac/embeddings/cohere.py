"""Cohere embeddings."""
from typing import TYPE_CHECKING, ClassVar, Optional

import numpy as np
from typing_extensions import override

from ..env import env
from ..schema import Item
from ..signal import TextEmbeddingSignal
from ..splitters.spacy_splitter import clustering_spacy_chunker
from ..tasks import TaskExecutionType
from .embedding import chunked_compute_embedding

if TYPE_CHECKING:
  from cohere import Client

COHERE_EMBED_MODEL = 'embed-english-light-v3.0'


class Cohere(TextEmbeddingSignal):
  """Computes embeddings using Cohere's embedding API.

  <br>**Important**: This will send data to an external server!

  <br>To use this signal, you must get a Cohere API key from
  [cohere.com/embed](https://cohere.com/embed) and add it to your .env.local.

  <br>For details on pricing, see: https://cohere.com/pricing.
  """

  name: ClassVar[str] = 'cohere'
  display_name: ClassVar[str] = 'Cohere Embeddings'
  local_batch_size: ClassVar[int] = 96
  local_parallelism: ClassVar[int] = 10
  local_strategy: ClassVar[TaskExecutionType] = 'threads'

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
      raise ImportError(
        'Could not import the "cohere" python package. '
        'Please install it with `pip install cohere`.'
      )

  @override
  def compute(self, docs: list[str]) -> list[Optional[Item]]:
    """Compute embeddings for the given documents."""
    cohere_input_type = 'search_document' if self.embed_input_type == 'document' else 'search_query'

    def _embed_fn(docs: list[str]) -> list[np.ndarray]:
      return [
        np.array(e)
        for e in self._model.embed(
          docs, truncate='END', model=COHERE_EMBED_MODEL, input_type=cohere_input_type
        ).embeddings
      ]

    return chunked_compute_embedding(
      _embed_fn, docs, self.local_batch_size, chunker=clustering_spacy_chunker
    )
