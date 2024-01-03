"""Jina embeddings hosted on Lilac's Garden."""
import gc
from typing import ClassVar, Iterator

import modal
from numpy.linalg import norm
from typing_extensions import override

from ..batch_utils import compress_docs
from ..schema import Item, lilac_embedding
from ..signal import TextEmbeddingSignal
from ..tasks import TaskExecutionType

JINA_CONTEXT_SIZE = 8192


class JinaV2SmallGarden(TextEmbeddingSignal):
  """Jina V2 Embeddings with 8K context, hosted on Lilac Garden.

  Each document is truncated to 8K characters, and the embeddings are computed on the truncated
  document.
  """

  name: ClassVar[str] = 'jina-v2-small-garden'
  display_name: ClassVar[str] = 'Jina V2 (small) on Garden'
  map_batch_size: ClassVar[int] = -1
  map_strategy: ClassVar[TaskExecutionType] = 'threads'

  @override
  def compute(self, docs: Iterator[str]) -> Iterator[Item]:
    """Call the embedding function."""
    trimmed_docs: list[str] = []
    doc_lengths: list[int] = []
    for doc in docs:
      trimmed_docs.append(doc[:JINA_CONTEXT_SIZE])
      doc_lengths.append(len(doc))
    gzipped_docs = compress_docs(trimmed_docs)

    del trimmed_docs, docs
    gc.collect()

    index = 0
    jina_batch = modal.Function.lookup('jina-batch', 'embed')
    for batch in jina_batch.remote_gen({'gzipped_docs': gzipped_docs}):
      batch /= norm(batch, axis=1, keepdims=True)
      for vector in batch:
        yield [lilac_embedding(start=0, end=doc_lengths[index], embedding=vector)]
        index += 1
