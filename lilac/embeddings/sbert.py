"""Sentence-BERT embeddings. Open-source models, designed to run on device."""
from typing import TYPE_CHECKING, ClassVar, Iterable, Iterator, cast

from typing_extensions import override

if TYPE_CHECKING:
  from sentence_transformers import SentenceTransformer
import gc

from ..schema import Item, RichData
from ..signal import TextEmbeddingSignal
from ..splitters.spacy_splitter import clustering_spacy_chunker
from .embedding import compute_split_embeddings
from .transformer_utils import SENTENCE_TRANSFORMER_BATCH_SIZE, setup_model_device

# The `all-mpnet-base-v2` model provides the best quality, while `all-MiniLM-L6-v2`` is 5 times
# faster and still offers good quality. See https://www.sbert.net/docs/pretrained_models.html#sentence-embedding-models/
MINI_LM_MODEL = 'all-MiniLM-L6-v2'


class SBERT(TextEmbeddingSignal):
  """Computes embeddings using Sentence-BERT library."""

  name: ClassVar[str] = 'sbert'
  display_name: ClassVar[str] = 'SBERT Embeddings'
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
    self._model.cpu()
    del self._model
    gc.collect()

    try:
      import torch

      torch.cuda.empty_cache()
    except ImportError:
      pass
