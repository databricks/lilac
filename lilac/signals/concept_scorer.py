"""A signal to compute a score along a concept."""
from typing import ClassVar, Iterable, Optional

import numpy as np
from typing_extensions import override

from ..auth import UserInfo
from ..batch_utils import flat_batched_compute
from ..concepts.concept import DRAFT_MAIN, ConceptModel
from ..concepts.db_concept import DISK_CONCEPT_MODEL_DB, ConceptModelDB
from ..embeddings.embedding import get_embed_fn
from ..embeddings.vector_store import VectorDBIndex
from ..schema import Field, Item, PathKey, RichData, SignalInputType, SpanVector, field, lilac_span
from ..signal import VectorSignal


class ConceptSignal(VectorSignal):
  """Compute scores along a given concept for documents."""

  name: ClassVar[str] = 'concept_score'
  input_type: ClassVar[SignalInputType] = SignalInputType.TEXT

  display_name: ClassVar[str] = 'Concept'

  namespace: str
  concept_name: str
  # This is set during setup and used in the UI to show the concept version on hover.
  version: Optional[int] = None

  # The draft version of the concept to use. If not provided, the latest version is used.
  draft: str = DRAFT_MAIN

  _concept_model_db: ConceptModelDB = DISK_CONCEPT_MODEL_DB
  _user: Optional[UserInfo] = None

  @override
  def fields(self) -> Field:
    return field(
      fields=[
        field(
          dtype='string_span',
          fields={
            'score': field(
              'float32', bins=[('Not in concept', None, 0.5), ('In concept', 0.5, None)]
            )
          },
        )
      ]
    )

  def set_user(self, user: Optional[UserInfo]) -> None:
    """Set the user for this signal."""
    self._user = user

  def _get_concept_model(self) -> ConceptModel:
    return self._concept_model_db.sync(
      self.namespace, self.concept_name, self.embedding, self._user, create=True
    )

  def _score_span_vectors(
    self, span_vectors: Iterable[Iterable[SpanVector]]
  ) -> Iterable[Optional[Item]]:
    concept_model = self._get_concept_model()

    return flat_batched_compute(
      span_vectors,
      f=lambda vectors: self._compute_span_vector_batch(vectors, concept_model),
      batch_size=concept_model.batch_size,
    )

  def _compute_span_vector_batch(
    self, span_vectors: Iterable[SpanVector], concept_model: ConceptModel
  ) -> list[Item]:
    vectors = [sv['vector'] for sv in span_vectors]
    spans = [sv['span'] for sv in span_vectors]
    scores = concept_model.score_embeddings(self.draft, np.array(vectors)).tolist()
    return [lilac_span(start, end, {'score': score}) for score, (start, end) in zip(scores, spans)]

  @override
  def setup(self) -> None:
    concept_model = self._get_concept_model()
    self.version = concept_model.version

  @override
  def compute(self, examples: Iterable[RichData]) -> Iterable[Optional[Item]]:
    """Get the scores for the provided examples."""
    embed_fn = get_embed_fn(self.embedding, split=True)
    span_vectors = embed_fn(examples)
    return self._score_span_vectors(span_vectors)

  @override
  def vector_compute(
    self, keys: Iterable[PathKey], vector_index: VectorDBIndex
  ) -> Iterable[Optional[Item]]:
    span_vectors = vector_index.get(keys)
    return self._score_span_vectors(span_vectors)

  @override
  def vector_compute_topk(
    self, topk: int, vector_index: VectorDBIndex, rowids: Optional[Iterable[str]] = None
  ) -> list[tuple[PathKey, Optional[Item]]]:
    concept_model = self._get_concept_model()
    query: np.ndarray = concept_model.coef(self.draft).astype(np.float32)
    query /= np.linalg.norm(query)
    topk_keys = [key for key, _ in vector_index.topk(query, topk, rowids)]
    return list(zip(topk_keys, self.vector_compute(topk_keys, vector_index)))

  @override
  def key(self, is_computed_signal: Optional[bool] = False) -> str:
    suffix = '/preview' if not is_computed_signal else ''
    # NOTE: The embedding is a value so already exists in the path structure. This means we do not
    # need to provide the name as part of the key, which still guarantees uniqueness.
    return f'{self.namespace}/{self.concept_name}/{self.embedding}{suffix}'
