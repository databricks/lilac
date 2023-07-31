"""A signal to compute a score along a concept."""
from typing import Iterable, Optional

import numpy as np
from typing_extensions import override

from ..auth import UserInfo
from ..concepts.concept import DEFAULT_NUM_NEG_EXAMPLES, DRAFT_MAIN, ConceptColumnInfo, ConceptModel
from ..concepts.db_concept import DISK_CONCEPT_MODEL_DB, ConceptModelDB
from ..data.dataset_utils import lilac_span
from ..embeddings.vector_store import VectorDBIndex
from ..schema import Field, Item, PathKey, RichData, field
from .signal import TextEmbeddingModelSignal


class ConceptScoreSignal(TextEmbeddingModelSignal):
  """Compute scores along a given concept for documents."""
  name = 'concept_score'
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
  def compute(self, data: Iterable[RichData]) -> Iterable[Optional[Item]]:
    concept_model = self._get_concept_model()
    return concept_model.score(self.draft, data)

  @override
  def vector_compute(self, keys: Iterable[PathKey],
                     vector_index: VectorDBIndex) -> Iterable[Optional[Item]]:
    concept_model = self._get_concept_model()
    all_vector_spans = vector_index.get(keys)
    # TODO(smilkov): Do this with batched computation.
    for vector_spans in all_vector_spans:
      embeddings = np.array([vector_span['vector'] for vector_span in vector_spans])
      scores = concept_model.score_embeddings(self.draft, embeddings)
      res: Item = []
      for vector_span, score in zip(vector_spans, scores):
        start, end = vector_span['span']
        res.append(lilac_span(start, end, {'score': score}))
      yield res

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
