"""Gegeral Text Embeddings (GTE) model. Open-source model, designed to run on device."""
import gc
from typing import TYPE_CHECKING, ClassVar, Iterator, Optional

import modal
import numpy as np
from typing_extensions import override

from ..utils import DebugTimer, chunks

if TYPE_CHECKING:
  from sentence_transformers import SentenceTransformer

from ..schema import Item, lilac_embedding
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
GTE_REMOTE_BATCH_SIZE = 1024


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
  runs_remote: ClassVar[bool] = True

  _model_name = GTE_SMALL
  _model: 'SentenceTransformer'

  @override
  def setup(self) -> None:
    print('setting up the model')
    try:
      from sentence_transformers import SentenceTransformer
    except ImportError:
      raise ImportError(
        'Could not import the "sentence_transformers" python package. '
        'Please install it with `pip install "sentence_transformers".'
      )
    self._model = setup_model_device(SentenceTransformer(self._model_name), self._model_name)

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
  def compute_remote(self, docs: Iterator[str]) -> Iterator[Item]:
    # Trim the docs to the max context size.
    trimmed_docs = [doc[:GTE_CONTEXT_SIZE] for doc in docs]

    with DebugTimer('Chunking'):
      text_chunks = [
        (i, chunk) for i, doc in enumerate(trimmed_docs) for chunk in clustering_spacy_chunker(doc)
      ]
    chunk_texts = [chunk[0] for _, chunk in text_chunks]
    doc_outputs: list[list[Item]] = [[] for _ in trimmed_docs]
    batches = [{'docs': texts} for texts in chunks(chunk_texts, GTE_REMOTE_BATCH_SIZE)]

    gte = modal.Function.lookup('gte', 'GTE.embed')
    all_vectors: list[np.ndarray] = []
    with DebugTimer('GTE remote'):
      for response in gte.map(batches):
        all_vectors.extend(list(response['vectors']))

    for vector, (i, (_, (start, end))) in zip(all_vectors, text_chunks):
      doc_outputs[i].append(lilac_embedding(start, end, vector))

    for doc_output in doc_outputs:
      yield doc_output

  @override
  def teardown(self) -> None:
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

  _model_name = GTE_BASE


class GTETiny(GTESmall):
  """Computes Gegeral Text Embeddings (GTE)."""

  name: ClassVar[str] = 'gte-tiny'
  display_name: ClassVar[str] = 'Gegeral Text Embeddings (tiny)'

  _model_name = GTE_TINY
