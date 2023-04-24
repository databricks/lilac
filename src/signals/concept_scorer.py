"""A signal to compute a score along a concept."""
from typing import Any, Iterable, Optional

from typing_extensions import override

from ..concepts.db_concept import DISK_CONCEPT_MODEL_DB, ConceptModelDB
from ..embeddings.vector_store import VectorStore
from ..schema import DataType, EnrichmentType, Field, ItemValue, Path, RichData
from .signal import Signal


class ConceptScoreSignal(Signal):
  """Compute scores along a "concept" for documents."""
  name = 'concept_score'
  enrichment_type = EnrichmentType.TEXT
  embedding_based = True

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

  @override
  def compute(self,
              data: Optional[Iterable[RichData]] = None,
              keys: Optional[Iterable[str]] = None,
              vector_store: Optional[VectorStore] = None) -> Iterable[Optional[ItemValue]]:
    if data and keys:
      raise ValueError(
          '"data" and "keys" cannot both be provided for ConceptScoreSignal.compute().')

    concept_model = self._concept_model_db.get(self.namespace, self.concept_name,
                                               self.embedding_name)
    if not self._concept_model_db.in_sync(concept_model):
      raise ValueError(
          f'Concept model "{self.namespace}/{self.concept_name}/{self.embedding_name}" '
          'is out of sync with its concept')

    if data:
      return concept_model.score(data)

    if not vector_store:
      raise ValueError(
          '"vector_store" is required in ConceptScoreSignal.compute() when passing "keys"')

    embeddings = vector_store.get(keys)
    return concept_model.score_embeddings(embeddings).tolist()
