"""Gegeral Text Embeddings (GTE) model. Open-source model, designed to run on device."""
import gc
from typing import TYPE_CHECKING, ClassVar, Optional

import numpy as np
from typing_extensions import override

if TYPE_CHECKING:
  from sentence_transformers import SentenceTransformer

import functools

from ..schema import Item
from ..signal import TextEmbeddingSignal
from ..splitters.spacy_splitter import clustering_spacy_chunker
from ..tasks import TaskExecutionType
from .embedding import chunked_compute_embedding
from .transformer_utils import SENTENCE_TRANSFORMER_BATCH_SIZE, setup_model_device

# See https://huggingface.co/spaces/mteb/leaderboard for leaderboard of models.
NOMIC_EMBED = 'nomic-ai/nomic-embed-text-v1.5'


@functools.cache
def _get_and_cache_model(model_name: str) -> 'SentenceTransformer':
  try:
    from sentence_transformers import SentenceTransformer
  except ImportError:
    raise ImportError(
      'Could not import the "sentence_transformers" python package. '
      'Please install it with `pip install "sentence_transformers".'
    )
  return setup_model_device(SentenceTransformer(model_name, trust_remote_code=True), model_name)


class NomicEmbed15(TextEmbeddingSignal):
  """Computes Nomic Embeddings 1.5 full (768 dimensions).

  <br>This embedding runs on-device. See the [model card](https://huggingface.co/nomic-ai/nomic-embed-text-v1.5)
  for details.
  """

  name: ClassVar[str] = 'nomic-embed-1.5-768'
  display_name: ClassVar[str] = 'Nomic Embeddings 1.5 784'
  local_batch_size: ClassVar[int] = SENTENCE_TRANSFORMER_BATCH_SIZE
  local_parallelism: ClassVar[int] = 1
  local_strategy: ClassVar[TaskExecutionType] = 'threads'
  supports_garden: ClassVar[bool] = False

  _model_name = NOMIC_EMBED
  _model: 'SentenceTransformer'
  _matryoshka_dim = 768

  @override
  def setup(self) -> None:
    self._model = _get_and_cache_model(self._model_name)

  @override
  def compute(self, docs: list[str]) -> list[Optional[Item]]:
    """Call the embedding function."""
    try:
      import torch.nn.functional as F
    except ImportError:
      raise ImportError(
        'Could not import the "sentence_transformers" python package. '
        'Please install it with `pip install "sentence_transformers".'
      )

    def _encode(doc: list[str]) -> list[np.ndarray]:
      embeddings = self._model.encode(doc, convert_to_tensor=True)
      # Extract the dense vectors from the model.
      embeddings = F.layer_norm(embeddings, normalized_shape=(embeddings.shape[1],))
      embeddings = embeddings[:, : self._matryoshka_dim]
      return embeddings.cpu().numpy()

    # While we get docs in batches of 1024, the chunker expands that by a factor of 3-10.
    # The sentence transformer API actually does batching internally, so we pass
    # local_batch_size * 16 to allow the library to see all the chunks at once.
    return chunked_compute_embedding(
      _encode, docs, self.local_batch_size * 16, chunker=clustering_spacy_chunker
    )

  @override
  def teardown(self) -> None:
    if not hasattr(self, '_model'):
      return

    self._model.cpu()
    del self._model
    gc.collect()

    try:
      import torch

      torch.cuda.empty_cache()
    except ImportError:
      pass


class NomicEmbed15_256(NomicEmbed15):
  """Computes Nomic Embeddings 1.5 (256 dimensions).

  <br>This embedding runs on-device. See the [model card](https://huggingface.co/nomic-ai/nomic-embed-text-v1.5)
  for details.
  """

  name: ClassVar[str] = 'nomic-embed-1.5-256'
  display_name: ClassVar[str] = 'Nomic Embeddings 1.5 256'
  _matryoshka_dim = 256
