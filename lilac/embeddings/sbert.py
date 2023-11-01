"""Sentence-BERT embeddings. Open-source models, designed to run on device."""
from typing import ClassVar, Iterable, cast

from typing_extensions import override

from ..schema import Item, RichData
from ..signal import TextEmbeddingSignal
from ..splitters.spacy_splitter import clustering_spacy_chunker
from .embedding import compute_split_embeddings
from .transformer_utils import SENTENCE_TRANSFORMER_BATCH_SIZE, get_model

# The `all-mpnet-base-v2` model provides the best quality, while `all-MiniLM-L6-v2`` is 5 times
# faster and still offers good quality. See https://www.sbert.net/docs/pretrained_models.html#sentence-embedding-models/
MINI_LM_MODEL = 'all-MiniLM-L6-v2'


class SBERT(TextEmbeddingSignal):
  """Computes embeddings using Sentence-BERT library."""

  name: ClassVar[str] = 'sbert'
  display_name: ClassVar[str] = 'SBERT Embeddings'

  @override
  def compute(self, docs: Iterable[RichData]) -> Iterable[Item]:
    """Call the embedding function."""
    model = get_model(MINI_LM_MODEL)
    embed_fn = model.encode
    split_fn = clustering_spacy_chunker if self._split else None
    docs = cast(Iterable[str], docs)
    yield from compute_split_embeddings(
      docs, batch_size=SENTENCE_TRANSFORMER_BATCH_SIZE, embed_fn=embed_fn, split_fn=split_fn
    )
