"""Sentence-BERT embeddings. Open-source models, designed to run on device."""
from typing import TYPE_CHECKING, ClassVar, Optional

from typing_extensions import override

from ..tasks import TaskExecutionType

if TYPE_CHECKING:
  from sentence_transformers import SentenceTransformer
import gc

from ..schema import Item
from ..signal import TextEmbeddingSignal
from ..splitters.spacy_splitter import clustering_spacy_chunker
from .embedding import chunked_compute_embedding
from .transformer_utils import SENTENCE_TRANSFORMER_BATCH_SIZE, setup_model_device

# The `all-mpnet-base-v2` model provides the best quality, while `all-MiniLM-L6-v2`` is 5 times
# faster and still offers good quality. See https://www.sbert.net/docs/pretrained_models.html#sentence-embedding-models/
MINI_LM_MODEL = 'all-MiniLM-L6-v2'


class SBERT(TextEmbeddingSignal):
  """Computes embeddings using Sentence-BERT library."""

  name: ClassVar[str] = 'sbert'
  display_name: ClassVar[str] = 'SBERT Embeddings'
  local_batch_size: ClassVar[int] = SENTENCE_TRANSFORMER_BATCH_SIZE
  local_parallelism: ClassVar[int] = 1
  local_strategy: ClassVar[TaskExecutionType] = 'threads'
  _model: 'SentenceTransformer'

  @override
  def setup(self) -> None:
    try:
      from sentence_transformers import SentenceTransformer
    except ImportError:
      raise ImportError(
        'Could not import the "sentence_transformers" python package. '
        'Please install it with `pip install "sentence_transformers".'
      )
    self._model = setup_model_device(SentenceTransformer(MINI_LM_MODEL), MINI_LM_MODEL)

  @override
  def compute(self, docs: list[str]) -> list[Optional[Item]]:
    """Call the embedding function."""
    # While we get docs in batches of 1024, the chunker expands that by a factor of 3-10.
    # The sentence transformer API actually does batching internally, so we pass
    # local_batch_size * 16 to allow the library to see all the chunks at once.
    return chunked_compute_embedding(
      self._model.encode, docs, self.local_batch_size * 16, chunker=clustering_spacy_chunker
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
