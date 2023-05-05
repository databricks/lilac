"""A signal to compute a score along a concept."""
from typing import Any, Iterable, Optional

import numpy as np
from typing_extensions import override

from ..concepts.concept import ConceptModel
from ..concepts.db_concept import DISK_CONCEPT_MODEL_DB, ConceptModelDB
from ..embeddings.vector_store import VectorStore
from ..schema import DataType, EnrichmentType, Field, ItemValue, PathTuple, RichData
from .signal import Signal
from .signal_registry import get_signal_cls


class ConceptScoreSignal(Signal):
  """Compute scores along a "concept" for documents."""
  name = 'concept_score'
  enrichment_type = EnrichmentType.TEXT_EMBEDDING

  namespace: str
  concept_name: str
  embedding_name: str

  _concept_model_db: ConceptModelDB

  def __init__(self, **data: Any):
    super().__init__(**data)

    self._concept_model_db = DISK_CONCEPT_MODEL_DB

    # Make sure that the embedding signal exists.
    try:
      get_signal_cls(self.embedding_name)
    except Exception as e:
      raise ValueError(
          f'Embedding signal "{self.embedding_name}" not found in the registry.') from e

  @override
  def fields(self) -> Field:
    return Field(dtype=DataType.FLOAT32)

  def _get_concept_model(self) -> ConceptModel:
    concept_model = self._concept_model_db.get(self.namespace, self.concept_name,
                                               self.embedding_name)
    if not self._concept_model_db.in_sync(concept_model):
      raise ValueError(
          f'Concept model "{self.namespace}/{self.concept_name}/{self.embedding_name}" '
          'is out of sync with its concept')
    return concept_model

  @override
  def compute(self, data: Iterable[RichData]) -> Iterable[Optional[ItemValue]]:
    concept_model = self._get_concept_model()
    return concept_model.score(data)

  @override
  def vector_compute(self, keys: Iterable[PathTuple],
                     vector_store: VectorStore) -> Iterable[Optional[ItemValue]]:
    concept_model = self._get_concept_model()
    embeddings = vector_store.get(keys)
    return concept_model.score_embeddings(embeddings).tolist()

  @override
  def vector_compute_topk(
      self,
      topk: int,
      vector_store: VectorStore,
      keys: Optional[Iterable[PathTuple]] = None) -> list[tuple[PathTuple, Optional[ItemValue]]]:
    concept_model = self._get_concept_model()
    query: np.ndarray = concept_model._model.coef_.flatten()
    topk_keys = [key for key, _ in vector_store.topk(query, topk, keys)]
    return list(zip(topk_keys, self.vector_compute(topk_keys, vector_store)))

  @override
  def key(self) -> str:
    # NOTE: The embedding is an entity so already exists in the path structure. This means we do not
    # need to provide the name as part of the key, which still guarantees uniqueness.
    return f'{self.namespace}/{self.concept_name}'
