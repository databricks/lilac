"""Gegeral Text Embeddings (GTE) model. Open-source model, designed to run on device."""
import gc
from typing import TYPE_CHECKING, ClassVar, Iterator, Optional

from typing_extensions import override

if TYPE_CHECKING:
  from FlagEmbedding import BGEM3FlagModel


import functools

from ..schema import Item
from ..signal import TextEmbeddingSignal
from ..splitters.spacy_splitter import clustering_spacy_chunker
from ..tasks import TaskExecutionType
from .embedding import chunked_compute_embedding
from .transformer_utils import SENTENCE_TRANSFORMER_BATCH_SIZE, setup_model_device

# See https://huggingface.co/spaces/mteb/leaderboard for leaderboard of models.
BGE_M3 = 'BAAI/bge-m3'


@functools.cache
def _get_and_cache_bge_m3(model_name: str) -> 'BGEM3FlagModel':
  try:
    from FlagEmbedding import BGEM3FlagModel
  except ImportError:
    raise ImportError(
      'Could not import the "FlagEmbedding" python package. '
      'Please install it with `pip install "lilac[bge]".'
    )
  model = BGEM3FlagModel(
    'BAAI/bge-m3', use_fp16=True
  )  # Setting use_fp16 to True speeds up computation with a slight performance degradation
  return model
  return setup_model_device(model, model_name)


class BGEM3(TextEmbeddingSignal):
  """Computes BGE-M3 embeddings.

  <br>This embedding runs on-device. See the [model card](https://huggingface.co/BAAI/bge-m3)
  for details.
  """

  name: ClassVar[str] = 'bge-m3'
  display_name: ClassVar[str] = 'BGE-M3'
  local_batch_size: ClassVar[int] = SENTENCE_TRANSFORMER_BATCH_SIZE
  local_parallelism: ClassVar[int] = 1
  local_strategy: ClassVar[TaskExecutionType] = 'threads'
  supports_garden: ClassVar[bool] = False

  _model_name = BGE_M3
  _model: 'BGEM3FlagModel'

  @override
  def setup(self) -> None:
    self._model = _get_and_cache_bge_m3(self._model_name)

  @override
  def compute(self, docs: list[str]) -> list[Optional[Item]]:
    """Call the embedding function."""

    def _encode(doc):
      # Extract the dense vectors from the model.
      return self._model.encode(doc)['dense_vecs']

    # While we get docs in batches of 1024, the chunker expands that by a factor of 3-10.
    # The sentence transformer API actually does batching internally, so we pass
    # local_batch_size * 16 to allow the library to see all the chunks at once.
    return chunked_compute_embedding(
      _encode, docs, self.local_batch_size * 16, chunker=clustering_spacy_chunker
    )

  @override
  def compute_garden(self, docs: Iterator[str]) -> Iterator[Item]:
    raise NotImplementedError('Garden computation is not supported for BGE-M3.')

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
