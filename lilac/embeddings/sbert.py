"""Sentence-BERT embeddings. Open-source models, designed to run on device."""
from typing import Iterable, cast

from typing_extensions import override

from ..schema import Item, RichData
from ..signal import TextEmbeddingSignal
from ..splitters.chunk_splitter import split_text
from .embedding import compute_split_embeddings
from .transformer_utils import get_model

# The `all-mpnet-base-v2` model provides the best quality, while `all-MiniLM-L6-v2`` is 5 times
# faster and still offers good quality. See https://www.sbert.net/docs/pretrained_models.html#sentence-embedding-models/
MINI_LM_MODEL = 'all-MiniLM-L6-v2'

# Maps a tuple of model name and device to the optimal batch size, found empirically.
_OPTIMAL_BATCH_SIZES: dict[str, dict[str, int]] = {
  MINI_LM_MODEL: {
    '': 64,  # Default batch size.
    'mps': 256,
  }
}


class SBERT(TextEmbeddingSignal):
  """Computes embeddings using Sentence-BERT library."""

  name = 'sbert'
  display_name = 'SBERT Embeddings'

  @override
  def compute(self, docs: Iterable[RichData]) -> Iterable[Item]:
    """Call the embedding function."""
    batch_size, model = get_model(MINI_LM_MODEL, _OPTIMAL_BATCH_SIZES[MINI_LM_MODEL])
    embed_fn = model.encode
    split_fn = split_text if self._split else None
    docs = cast(Iterable[str], docs)
    yield from compute_split_embeddings(docs, batch_size, embed_fn=embed_fn, split_fn=split_fn)
