"""PaLM embeddings."""
from typing import ClassVar, Iterable, cast

import numpy as np
from tenacity import retry, stop_after_attempt, wait_fixed, wait_random_exponential
from typing_extensions import override

from ..env import env
from ..schema import Item, RichData
from ..signal import TextEmbeddingSignal
from ..splitters.spacy_splitter import clustering_spacy_chunker
from .embedding import compute_split_embeddings

PALM_BATCH_SIZE = 1  # PaLM API only supports batch size 1.
API_NUM_PARALLEL_REQUESTS = 256  # Because batch size is 1, we can send many requests in parallel.
GCP_NUM_PARALLEL_REQUESTS = 3  # We aim for 600 requests per minute
API_EMBEDDING_MODEL = 'models/embedding-gecko-001'
GCP_EMBEDDING_MODEL = 'textembedding-gecko@001'


class PaLM(TextEmbeddingSignal):
  """Computes embeddings using PaLM's embedding API.

  <br>**Important**: This will send data to an external server!

  <br>To use this signal, you must get a PaLM API key from
  [makersuite.google.com](https://makersuite.google.com/app/apikey) and add it to your .env.local.
  """

  name: ClassVar[str] = 'palm'
  display_name: ClassVar[str] = 'PaLM Embeddings'

  @override
  def setup(self) -> None:
    api_key = env('PALM_API_KEY')
    gcp_project_id = env('GCP_PROJECT_ID')
    if not api_key and not gcp_project_id:
      raise ValueError(
        'Neither `PALM_API_KEY` or `GCP_PROJECT_ID` environment variables'
        ' are set, please provide one.'
      )
    if api_key:
      try:
        import google.generativeai as palm

        palm.configure(api_key=api_key)
        self._connector = 'api'
        self._num_parallel_requests = API_NUM_PARALLEL_REQUESTS
        self._model = palm.generate_embeddings
      except ImportError:
        raise ImportError(
          'Could not import the "google.generativeai" python package. '
          'Please install it with `pip install google-generativeai`.'
        )
    if gcp_project_id:
      try:
        from google.cloud import aiplatform
        from vertexai.language_models import TextEmbeddingModel

        aiplatform.init(project=gcp_project_id)
        self._connector = 'vertex'
        self._model = TextEmbeddingModel.from_pretrained(GCP_EMBEDDING_MODEL)
        self._num_parallel_requests = GCP_NUM_PARALLEL_REQUESTS
      except ImportError:
        raise ImportError(
          'Could not import the "vertex" python package. '
          'Please install it with `pip install google-cloud-aiplatform`.'
        )

  @override
  def compute(self, docs: Iterable[RichData]) -> Iterable[Item]:
    """Compute embeddings for the given documents."""
    if self._connector == 'api':

      @retry(wait=wait_random_exponential(min=1, max=20), stop=stop_after_attempt(10))
      def embed_fn(texts: list[str]) -> list[np.ndarray]:
        assert len(texts) == 1, 'PaLM API only supports batch size 1.'
        response = self._model(model=API_EMBEDDING_MODEL, text=texts[0])
        return [np.array(response['embedding'], dtype=np.float32)]

    elif self._connector == 'vertex':

      @retry(wait=wait_fixed(5), stop=stop_after_attempt(15))
      def embed_fn(texts: list[str]) -> list[np.ndarray]:
        assert len(texts) <= 5, 'Vertex currently support a batch size of 5.'
        response = self._model.get_embeddings([texts[0]])[0].values
        return [np.array(response, dtype=np.float32)]

    docs = cast(Iterable[str], docs)
    split_fn = clustering_spacy_chunker if self._split else None
    yield from compute_split_embeddings(
      docs, PALM_BATCH_SIZE, embed_fn, split_fn, num_parallel_requests=self._num_parallel_requests
    )
