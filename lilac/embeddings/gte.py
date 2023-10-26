"""Gegeral Text Embeddings (GTE) model. Open-source model, designed to run on device."""
from typing import ClassVar, Iterable, cast

from typing_extensions import override

from ..schema import Item, RichData
from ..signal import TextEmbeddingSignal
from ..splitters.chunk_splitter import split_text
from .embedding import compute_split_embeddings
from .transformer_utils import get_model

# See https://huggingface.co/spaces/mteb/leaderboard for leaderboard of models.
GTE_SMALL = 'thenlper/gte-small'
GTE_BASE = 'thenlper/gte-base'
GTE_TINY = 'TaylorAI/gte-tiny'

# Maps a tuple of model name and device to the optimal batch size, found empirically.
_OPTIMAL_BATCH_SIZES: dict[str, dict[str, int]] = {
  GTE_TINY: {
    '': 64,  # Default batch size.
    'mps': 512,
  },
  GTE_SMALL: {
    '': 64,  # Default batch size.
    'mps': 256,
  },
  GTE_BASE: {
    '': 64,  # Default batch size.
    'mps': 128,
  }
}


class GTESmall(TextEmbeddingSignal):
  """Computes Gegeral Text Embeddings (GTE).

  <br>This embedding runs on-device. See the [model card](https://huggingface.co/thenlper/gte-small)
  for details.
  """

  name: ClassVar[str] = 'gte-small'
  display_name: ClassVar[str] = 'Gegeral Text Embeddings (small)'

  _model_name = GTE_SMALL

  @override
  def compute(self, docs: Iterable[RichData]) -> Iterable[Item]:
    """Call the embedding function."""
    batch_size, model = get_model(self._model_name, _OPTIMAL_BATCH_SIZES[self._model_name])
    embed_fn = model.encode
    split_fn = split_text if self._split else None
    docs = cast(Iterable[str], docs)
    yield from compute_split_embeddings(docs, batch_size, embed_fn=embed_fn, split_fn=split_fn)


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
