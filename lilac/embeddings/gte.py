"""Gegeral Text Embeddings (GTE) model. Open-source model, designed to run on device."""
import gc
import itertools
from typing import TYPE_CHECKING, ClassVar, Iterator, Optional

import modal
from typing_extensions import override

from ..batch_utils import compress_docs
from ..splitters.chunk_splitter import TextChunk
from ..utils import DebugTimer, chunks

if TYPE_CHECKING:
  from sentence_transformers import SentenceTransformer

import functools

from ..schema import Item, chunk_embedding
from ..signal import TextEmbeddingSignal
from ..splitters.spacy_splitter import clustering_spacy_chunker
from ..tasks import TaskExecutionType
from .embedding import chunked_compute_embedding
from .transformer_utils import SENTENCE_TRANSFORMER_BATCH_SIZE, setup_model_device

# See https://huggingface.co/spaces/mteb/leaderboard for leaderboard of models.
GTE_SMALL = 'thenlper/gte-small'
GTE_BASE = 'thenlper/gte-base'
GTE_TINY = 'TaylorAI/gte-tiny'
GTE_CONTEXT_SIZE = 512
GTE_REMOTE_BATCH_SIZE = 1024 * 16


@functools.cache
def _get_and_cache_model(model_name: str) -> 'SentenceTransformer':
  try:
    from sentence_transformers import SentenceTransformer
  except ImportError:
    raise ImportError(
      'Could not import the "sentence_transformers" python package. '
      'Please install it with `pip install "sentence_transformers".'
    )
  return setup_model_device(SentenceTransformer(model_name), model_name)


class GTESmall(TextEmbeddingSignal):
  """Computes Gegeral Text Embeddings (GTE).

  <br>This embedding runs on-device. See the [model card](https://huggingface.co/thenlper/gte-small)
  for details.
  """

  name: ClassVar[str] = 'gte-small'
  display_name: ClassVar[str] = 'Gegeral Text Embeddings (small)'
  local_batch_size: ClassVar[int] = SENTENCE_TRANSFORMER_BATCH_SIZE
  local_parallelism: ClassVar[int] = 1
  local_strategy: ClassVar[TaskExecutionType] = 'threads'
  supports_garden: ClassVar[bool] = True

  _model_name = GTE_SMALL
  _model: 'SentenceTransformer'

  @override
  def setup(self) -> None:
    self._model = _get_and_cache_model(self._model_name)

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
  def compute_garden(self, docs: Iterator[str]) -> Iterator[Item]:
    # Trim the docs to the max context size.

    trimmed_docs = (doc[:GTE_CONTEXT_SIZE] for doc in docs)
    text_chunks: Iterator[tuple[int, TextChunk]] = (
      (i, chunk) for i, doc in enumerate(trimmed_docs) for chunk in clustering_spacy_chunker(doc)
    )
    text_chunks, text_chunks_2 = itertools.tee(text_chunks)
    chunk_texts = (chunk[0] for _, chunk in text_chunks)

    batches = (
      {'gzipped_docs': compress_docs(texts)} for texts in chunks(chunk_texts, GTE_REMOTE_BATCH_SIZE)
    )

    gte = modal.Function.lookup('gte', 'GTE.embed')
    with DebugTimer('Computing GTE on Lilac Garden'):
      doc_embeddings: list[Item] = []
      last_index = 0
      for response in gte.map(batches, order_outputs=True):
        for vector in response['vectors']:
          i, (_, (start, end)) = next(text_chunks_2)
          if i > last_index:
            yield doc_embeddings
            doc_embeddings = []
            last_index = i
          doc_embeddings.append(chunk_embedding(start, end, vector))
      yield doc_embeddings

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


class GTEBase(GTESmall):
  """Computes Gegeral Text Embeddings (GTE).

  <br>This embedding runs on-device. See the [model card](https://huggingface.co/thenlper/gte-base)
  for details.
  """

  name: ClassVar[str] = 'gte-base'
  display_name: ClassVar[str] = 'Gegeral Text Embeddings (base)'

  supports_garden: ClassVar[bool] = False
  _model_name = GTE_BASE


class GTETiny(GTESmall):
  """Computes Gegeral Text Embeddings (GTE)."""

  name: ClassVar[str] = 'gte-tiny'
  display_name: ClassVar[str] = 'Gegeral Text Embeddings (tiny)'

  supports_garden: ClassVar[bool] = False
  _model_name = GTE_TINY
