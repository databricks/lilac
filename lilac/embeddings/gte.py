"""Gegeral Text Embeddings (GTE) model. Open-source model, designed to run on device."""
from typing import ClassVar, Iterable, cast

from typing_extensions import override

from ..schema import Item, RichData
from ..signal import TextEmbeddingSignal
from ..splitters.spacy_splitter import clustering_spacy_chunker
from .embedding import compute_split_embeddings
from .transformer_utils import SENTENCE_TRANSFORMER_BATCH_SIZE, get_model

# See https://huggingface.co/spaces/mteb/leaderboard for leaderboard of models.
GTE_SMALL = 'thenlper/gte-small'
GTE_BASE = 'thenlper/gte-base'
GTE_TINY = 'TaylorAI/gte-tiny'


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
    model = get_model(self._model_name)
    embed_fn = model.encode
    split_fn = clustering_spacy_chunker if self._split else None
    docs = cast(Iterable[str], docs)
    yield from compute_split_embeddings(
      docs, batch_size=SENTENCE_TRANSFORMER_BATCH_SIZE, embed_fn=embed_fn, split_fn=split_fn
    )


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
