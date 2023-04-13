"""A signal to compute a score along a concept."""
from typing import Any, Iterable, Optional

from typing_extensions import override

from ..concepts.db_concept import DISK_CONCEPT_MODEL_DB, ConceptModelDB
from ..embeddings.embedding_index import GetEmbeddingIndexFn
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
  def compute(
      self,
      data: Optional[Iterable[RichData]] = None,
      keys: Optional[Iterable[bytes]] = None,
      get_embedding_index: Optional[GetEmbeddingIndexFn] = None) -> Iterable[Optional[ItemValue]]:
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
      scores: Iterable[float] = concept_model.score(data)
    elif keys:
      if not get_embedding_index:
        raise ValueError(
            '"get_embedding_index" is required in ConceptScoreSignal.compute() when passing "keys"')
      embeddings = get_embedding_index(self.embedding_name, keys).embeddings
      scores = concept_model.score_embeddings(embeddings)
    return [float(score) for score in scores]
