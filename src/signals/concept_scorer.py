"""A signal to compute a score along a concept."""
import random
from typing import Any, Iterable, Optional, cast

import numpy as np
from typing_extensions import override

from ..concepts.concept import (
  DEFAULT_NUM_NEG_EXAMPLES,
  DRAFT_MAIN,
  ConceptDatasetInfo,
  LogisticEmbeddingModel,
  Sensitivity,
)
from ..concepts.db_concept import DISK_CONCEPT_MODEL_DB, ConceptModelDB
from ..data.dataset import Column, UnaryOp, val
from ..db_manager import get_dataset
from ..embeddings.vector_store import VectorStore
from ..schema import UUID_COLUMN, VALUE_KEY, DataType, Field, Item, RichData, VectorKey
from .signal import TextEmbeddingModelSignal
from .splitters.text_splitter_spacy import SentenceSplitterSpacy


class ConceptScoreSignal(TextEmbeddingModelSignal):
  """Compute scores along a given concept for documents."""
  name = 'concept_score'
  display_name = 'Concept'

  namespace: str
  concept_name: str

  # The draft version of the concept to use. If not provided, the latest version is used.
  draft: str = DRAFT_MAIN

  sensitivity = Sensitivity.BALANCED

  num_negative_examples = DEFAULT_NUM_NEG_EXAMPLES

  dataset: Optional[ConceptDatasetInfo] = None

  _concept_model_db: ConceptModelDB

  def __init__(self, **data: Any):
    super().__init__(**data)

    self._concept_model_db = DISK_CONCEPT_MODEL_DB

  @override
  def fields(self) -> Field:
    return Field(dtype=DataType.FLOAT32)

  def _get_logistic_model(self) -> LogisticEmbeddingModel:
    model = self._concept_model_db.get(self.namespace, self.concept_name, self.embedding,
                                       self.dataset)
    if not model:
      negative_examples: list[str] = []

      if self.dataset:
        # Sorting by UUID column will return examples with random order.
        dataset = get_dataset(self.dataset.namespace, self.dataset.name)
        path = self.dataset.path
        docs = dataset.select_rows([Column(val(path), alias='text')],
                                   filters=[(path, UnaryOp.EXISTS)],
                                   sort_by=[UUID_COLUMN],
                                   limit=self.num_negative_examples)
        docs = docs.df()['text']
        sentences = _split_docs_into_sentences(docs)
        # Choose a random unique subset of sentences.
        num_samples = min(self.num_negative_examples, len(sentences))
        negative_examples = random.sample(sentences, num_samples)

      model = self._concept_model_db.create(self.namespace, self.concept_name, self.embedding,
                                            self.dataset, negative_examples)
    self._concept_model_db.sync(model)
    return model.get_model(self.draft)

  @override
  def compute(self, data: Iterable[RichData]) -> Iterable[Optional[Item]]:
    logistic_model = self._get_logistic_model()
    return logistic_model.score(data, self.sensitivity)

  @override
  def vector_compute(self, keys: Iterable[VectorKey],
                     vector_store: VectorStore) -> Iterable[Optional[Item]]:
    logistic_model = self._get_logistic_model()
    embeddings = vector_store.get(keys)
    return logistic_model.score_embeddings(embeddings, self.sensitivity).tolist()

  @override
  def vector_compute_topk(
      self,
      topk: int,
      vector_store: VectorStore,
      keys: Optional[Iterable[VectorKey]] = None) -> list[tuple[VectorKey, Optional[Item]]]:
    logistic_model = self._get_logistic_model()
    query: np.ndarray = logistic_model._model.coef_.flatten()
    topk_keys = [key for key, _ in vector_store.topk(query, topk, keys)]
    return list(zip(topk_keys, self.vector_compute(topk_keys, vector_store)))

  @override
  def key(self) -> str:
    # NOTE: The embedding is a value so already exists in the path structure. This means we do not
    # need to provide the name as part of the key, which still guarantees uniqueness.
    return f'{self.namespace}/{self.concept_name}'


def _split_docs_into_sentences(docs: Iterable[str]) -> list[str]:
  splitter = SentenceSplitterSpacy()
  doc_spans = list(splitter.compute(docs))
  sentences: list[str] = []
  for sentence_spans, text in zip(doc_spans, docs):
    for span in cast(Iterable[Any], sentence_spans):
      start, end = span[VALUE_KEY]['start'], span[VALUE_KEY]['end']
      sentences.append(text[start:end])
  return sentences
