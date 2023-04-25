"""A signal to compute a score along a concept."""
from typing import Any, Iterable, Optional

from typing_extensions import override

from ..concepts.concept import ConceptModel
from ..concepts.db_concept import DISK_CONCEPT_MODEL_DB, ConceptModelDB
from ..embeddings.vector_store import VectorStore
from ..schema import DataType, EnrichmentType, Field, ItemValue, Path, RichData
from .signal import Signal


class ConceptScoreSignal(Signal):
  """Compute scores along a "concept" for documents."""
  name = 'concept_score'
  enrichment_type = EnrichmentType.TEXT
  vector_based = True

  namespace: str
  concept_name: str
  embedding_name: str

  _concept_model_db: ConceptModelDB

  def __init__(self, **data: Any):
    super().__init__(embedding=data.get('embedding_name'), **data)
    self._concept_model_db = DISK_CONCEPT_MODEL_DB

  @override
  def fields(self, input_column: Path) -> Field:
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
  def vector_compute(self, keys: Iterable[str],
                     vector_store: VectorStore) -> Iterable[Optional[ItemValue]]:
    concept_model = self._get_concept_model()
    embeddings = vector_store.get(keys)
    return concept_model.score_embeddings(embeddings).tolist()
