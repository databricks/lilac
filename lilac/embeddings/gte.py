"""Gegeral Text Embeddings (GTE) model. Open-source model, designed to run on device."""
from typing import TYPE_CHECKING, ClassVar, Iterable, Iterator, cast

from typing_extensions import override

if TYPE_CHECKING:
  from sentence_transformers import SentenceTransformer

from ..schema import Item, RichData
from ..signal import TextEmbeddingSignal
from ..splitters.spacy_splitter import clustering_spacy_chunker
from .embedding import compute_split_embeddings
from .transformer_utils import SENTENCE_TRANSFORMER_BATCH_SIZE, setup_model_device

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
    self._model = setup_model_device(SentenceTransformer(self._model_name), self._model_name)

  @override
  def compute(self, docs: Iterable[RichData]) -> Iterator[Item]:
    """Call the embedding function."""
    embed_fn = self._model.encode
    split_fn = clustering_spacy_chunker if self._split else None
    docs = cast(Iterable[str], docs)
    yield from compute_split_embeddings(
      docs, batch_size=SENTENCE_TRANSFORMER_BATCH_SIZE, embed_fn=embed_fn, split_fn=split_fn
    )

  @override
  def teardown(self) -> None:
    del self._model


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
