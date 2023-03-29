"""A signal to compute a score along a concept."""
from typing import Iterable, Optional

from typing_extensions import override

from ..concepts.concept import ConceptModel
from ..concepts.db_concept import DISK_CONCEPT_MODEL_DB, ConceptModelDB
from ..embeddings.embedding_index import GetEmbeddingIndexFn
from ..schema import DataType, EnrichmentType, Field, Item, RichData
from .signal import Signal

SCORE_FIELD_NAME = 'score'


class ConceptScoreSignal(Signal):
  """A signal to compute scores along a "concept" for documents."""
  name = 'concept_score'
  enrichment_type = EnrichmentType.TEXT
  embedding_based = True

  namespace: str
  concept_name: str
  embedding_name: str

  _concept_model: ConceptModel
  _concept_model_db: ConceptModelDB

  def __init__(self, **data: dict):
    super().__init__(**data)
    self._concept_model_db = DISK_CONCEPT_MODEL_DB
    concept_model = self._concept_model_db.get(self.namespace, self.concept_name,
                                               self.embedding_name)
    model_name = f'{self.namespace}/{self.concept_name}/{self.embedding_name}'
    if not concept_model:
      raise ValueError(f'Concept model "{model_name}" not found')
    if not self._concept_model_db.in_sync(self._concept_model):
      raise ValueError(f'Concept model "{model_name}" is out of sync with its concept')
    self._concept_model = concept_model

  @override
  def fields(self) -> dict[str, Field]:
    return {SCORE_FIELD_NAME: Field(dtype=DataType.FLOAT32)}

  @override
  def compute(
      self,
      data: Optional[Iterable[RichData]] = None,
      keys: Optional[Iterable[bytes]] = None,
      get_embedding_index: Optional[GetEmbeddingIndexFn] = None) -> Iterable[Optional[Item]]:
    if data and keys:
      raise ValueError(
          '"data" and "keys" cannot both be provided for ConceptScoreSignal.compute().')

    if not self._concept_model_db.in_sync(self._concept_model):
      raise ValueError(
          f'Concept model "{self.namespace}/{self.concept_name}/{self.embedding_name}" '
          'is out of sync with its concept')

    if data:
      scores: Iterable[float] = self._concept_model.score(data)
    elif keys:
      if not get_embedding_index:
        raise ValueError(
            '"get_embedding_index" is required in ConceptScoreSignal.compute() when passing "keys"')
      embeddings = get_embedding_index(self.embedding_name, keys).embeddings
      scores = self._concept_model.score_embeddings(embeddings)
    return [{SCORE_FIELD_NAME: float(score)} for score in scores]
