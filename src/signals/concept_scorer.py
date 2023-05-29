"""A signal to compute a score along a concept."""
from typing import Iterable, Optional

import numpy as np
from typing_extensions import override

from ..concepts.concept import (
  DEFAULT_NUM_NEG_EXAMPLES,
  DRAFT_MAIN,
  ConceptColumnInfo,
  ConceptModel,
  Sensitivity,
)
from ..concepts.db_concept import DISK_CONCEPT_MODEL_DB, ConceptModelDB
from ..embeddings.vector_store import VectorStore
from ..schema import DataType, Field, Item, RichData, VectorKey
from .signal import TextEmbeddingModelSignal


class ConceptScoreSignal(TextEmbeddingModelSignal):
  """Compute scores along a given concept for documents."""
  name = 'concept_score'
  display_name = 'Concept'

  namespace: str
  concept_name: str

  # The draft version of the concept to use. If not provided, the latest version is used.
  draft: str = DRAFT_MAIN

  # The sensitivity of the concept. See the `Sensitive` enum for more details.
  sensitivity = Sensitivity.BALANCED

  # Number of randomly chosen negative examples to use when training the concept. This is used to
  # obtain a better suited model for the concrete dataset.
  num_negative_examples = DEFAULT_NUM_NEG_EXAMPLES

  _dataset_info: Optional[ConceptColumnInfo] = None
  _concept_model_db: ConceptModelDB = DISK_CONCEPT_MODEL_DB

  @override
  def fields(self) -> Field:
    return Field(dtype=DataType.FLOAT32)

  def set_dataset_info(self, dataset_info: ConceptColumnInfo) -> None:
    """Set the dataset info for this signal."""
    self._dataset_info = dataset_info
    self._dataset_info.num_negative_examples = self.num_negative_examples

  def _get_concept_model(self) -> ConceptModel:
    model = self._concept_model_db.get(self.namespace, self.concept_name, self.embedding,
                                       self._dataset_info)
    if not model:
      model = self._concept_model_db.create(self.namespace, self.concept_name, self.embedding,
                                            self._dataset_info)
    self._concept_model_db.sync(model)
    return model

  @override
  def compute(self, data: Iterable[RichData]) -> Iterable[Optional[Item]]:
    concept_model = self._get_concept_model()
    return concept_model.score(self.draft, data, self.sensitivity)

  @override
  def vector_compute(self, keys: Iterable[VectorKey],
                     vector_store: VectorStore) -> Iterable[Optional[Item]]:
    concept_model = self._get_concept_model()
    embeddings = vector_store.get(keys)
    return concept_model.score_embeddings(self.draft, embeddings, self.sensitivity).tolist()

  @override
  def vector_compute_topk(
      self,
      topk: int,
      vector_store: VectorStore,
      keys: Optional[Iterable[VectorKey]] = None) -> list[tuple[VectorKey, Optional[Item]]]:
    concept_model = self._get_concept_model()
    query: np.ndarray = concept_model.coef(self.draft)
    topk_keys = [key for key, _ in vector_store.topk(query, topk, keys)]
    return list(zip(topk_keys, self.vector_compute(topk_keys, vector_store)))

  @override
  def key(self) -> str:
    # NOTE: The embedding is a value so already exists in the path structure. This means we do not
    # need to provide the name as part of the key, which still guarantees uniqueness.
    return f'{self.namespace}/{self.concept_name}'
