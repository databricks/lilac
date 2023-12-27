"""Cohere embeddings."""
from typing import TYPE_CHECKING, ClassVar

from typing_extensions import override

from ..env import env
from ..schema import Item
from ..signal import TextEmbeddingSignal
from ..splitters.spacy_splitter import clustering_spacy_chunker

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
  map_batch_size: int = 96
  map_parallelism: int = 10
  map_strategy = 'threads'

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
  def compute(self, docs: list[str]) -> list[Item]:
    """Compute embeddings for the given documents."""
    cohere_input_type = 'search_document' if self.embed_input_type == 'document' else 'search_query'
    texts = [(i, chunk) for i, doc in enumerate(docs) for chunk in clustering_spacy_chunker(doc)]
    output = [[] for _ in docs]
    batches = chunked(texts, self.map_batch_size)
    for batch in batches:
      batch_texts = [text for _, (text, _) in batch]
      batch_embeddings = self._model.embed(
        batch_texts, truncate='END', model=COHERE_EMBED_MODEL, input_type=cohere_input_type
      ).embeddings
      for (i, (_, (start, end))), embedding in zip(batch, batch_embeddings):
        output[i].append(lilac_embedding(start, end, embedding))
    return output
