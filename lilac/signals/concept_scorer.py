"""A signal to compute a score along a concept."""
import itertools
from typing import Iterable, Optional, cast

import numpy as np
from typing_extensions import override

from ..auth import UserInfo
from ..batch_utils import batched_span_vector_compute, flat_batched_compute
from ..concepts.concept import DEFAULT_NUM_NEG_EXAMPLES, DRAFT_MAIN, ConceptColumnInfo, ConceptModel
from ..concepts.db_concept import DISK_CONCEPT_MODEL_DB, ConceptModelDB
from ..data.dataset_utils import lilac_span
from ..embeddings.vector_store import SpanVector, VectorDBIndex
from ..schema import (
  TEXT_SPAN_END_FEATURE,
  TEXT_SPAN_START_FEATURE,
  VALUE_KEY,
  Field,
  Item,
  PathKey,
  RichData,
  SignalInputType,
  field,
)
from ..signals.signal import (
  EMBEDDING_KEY,
  TextEmbeddingSignal,
  VectorSignal,
  get_signal_by_type,
  get_signal_cls,
)


class ConceptScoreSignal(VectorSignal):
  """Compute scores along a given concept for documents."""
  name = 'concept_score'
  input_type = SignalInputType.TEXT

  display_name = 'Concept'

  namespace: str
  concept_name: str

  # The draft version of the concept to use. If not provided, the latest version is used.
  draft: str = DRAFT_MAIN

  # Number of randomly chosen negative examples to use when training the concept. This is used to
  # obtain a better suited model for the concrete dataset.
  num_negative_examples = DEFAULT_NUM_NEG_EXAMPLES

  _column_info: Optional[ConceptColumnInfo] = None
  _concept_model_db: ConceptModelDB = DISK_CONCEPT_MODEL_DB
  _user: Optional[UserInfo] = None

  @override
  def fields(self) -> Field:
    return field(fields=[
      field(
        dtype='string_span',
        fields={
          'score': field(
            'float32',
            bins=[('Not in concept', None, 0.5), ('In concept', 0.5, None)],
          )
        })
    ])

  def set_column_info(self, column_info: ConceptColumnInfo) -> None:
    """Set the dataset info for this signal."""
    self._column_info = column_info
    self._column_info.num_negative_examples = self.num_negative_examples

  def set_user(self, user: Optional[UserInfo]) -> None:
    """Set the user for this signal."""
    self._user = user

  def _get_concept_model(self) -> ConceptModel:
    model = self._concept_model_db.get(
      self.namespace, self.concept_name, self.embedding, self._column_info, user=self._user)
    if not model:
      model = self._concept_model_db.create(
        self.namespace, self.concept_name, self.embedding, self._column_info, user=self._user)

    self._concept_model_db.sync(model, self._user)
    return model

  @override
  def compute(self, examples: Iterable[RichData]) -> Iterable[Optional[Item]]:
    """Get the scores for the provided examples."""
    embedding_signal = get_signal_cls(self.embedding)()
    if not isinstance(embedding_signal, TextEmbeddingSignal):
      raise ValueError(f'Only text embedding signals are currently supported for concepts. '
                       f'"{self.embedding}" is a {type(embedding_signal)}.')

    embedding_cls = get_signal_by_type(self.embedding, TextEmbeddingSignal)
    embedding = embedding_cls(split=True)
    embedding.setup()

    embedding_items = embedding.compute(examples)
    span_vectors: Iterable[Iterable[SpanVector]] = ([{
      'vector': span_embedding[EMBEDDING_KEY],
      'span': (span_embedding[VALUE_KEY][TEXT_SPAN_START_FEATURE],
               span_embedding[VALUE_KEY][TEXT_SPAN_END_FEATURE])
    } for span_embedding in item] for item in cast(Iterable[Item], embedding_items))

    return self._score_span_vectors(span_vectors)

  def _score_span_vectors(self,
                          span_vectors: Iterable[Iterable[SpanVector]]) -> Iterable[Optional[Item]]:
    concept_model = self._get_concept_model()

    return batched_span_vector_compute(span_vectors)

    # NOTE: We use tee() here so we can iterate the input twice to zip the output of the batched
    # compute call to the span offsets instead of allowing the SpanVector and the resulting Item to
    # be a primitive value and avoid boxing the span vectors.
    (vectors_it, spans_it) = itertools.tee(span_vectors, 2)
    all_vectors = (
      [vector_span['vector'] for vector_span in vector_spans] for vector_spans in vectors_it)
    all_spans = ([vector_span['span'] for vector_span in vector_spans] for vector_spans in spans_it)

    all_scores = flat_batched_compute(
      input=all_vectors,
      f=lambda vectors: concept_model.score_embeddings(self.draft, np.array(vectors)).tolist(),
      batch_size=concept_model.batch_size)

    for scores, spans in zip(all_scores, all_spans):
      res: Item = []
      for score, span in zip(scores, spans):
        start, end = span
        res.append(lilac_span(start, end, {'score': score}))
      yield res

  @override
  def vector_compute(self, keys: Iterable[PathKey],
                     vector_index: VectorDBIndex) -> Iterable[Optional[Item]]:
    all_vector_spans = vector_index.get(keys)
    return self._score_span_vectors(all_vector_spans)

  @override
  def vector_compute_topk(
      self,
      topk: int,
      vector_index: VectorDBIndex,
      keys: Optional[Iterable[PathKey]] = None) -> list[tuple[PathKey, Optional[Item]]]:
    concept_model = self._get_concept_model()
    query: np.ndarray = concept_model.coef(self.draft)
    topk_keys = [key for key, _ in vector_index.topk(query, topk, keys)]
    return list(zip(topk_keys, self.vector_compute(topk_keys, vector_index)))

  @override
  def key(self, is_computed_signal: Optional[bool] = False) -> str:
    # NOTE: The embedding is a value so already exists in the path structure. This means we do not
    # need to provide the name as part of the key, which still guarantees uniqueness.
    version = f'/v{self._get_concept_model().version}' if is_computed_signal else ''
    return f'{self.namespace}/{self.concept_name}/{self.embedding}{version}'
