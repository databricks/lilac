"""Defines the concept and the concept models."""
import dataclasses
import random
from enum import Enum
from typing import Iterable, Literal, Optional, Union

import numpy as np
from pydantic import BaseModel, validator
from sklearn.exceptions import NotFittedError
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import KFold, cross_val_score

from ..db_manager import get_dataset
from ..embeddings.embedding import get_embed_fn
from ..schema import Path, RichData, SignalInputType, normalize_path
from ..signals.signal import EMBEDDING_KEY, TextEmbeddingSignal, get_signal_cls
from ..utils import DebugTimer

LOCAL_CONCEPT_NAMESPACE = 'local'

# Number of randomly sampled negative examples to use for training. This is used to obtain a more
# balanced model that works with a specific dataset.
DEFAULT_NUM_NEG_EXAMPLES = 300


class ConceptColumnInfo(BaseModel):
  """Information about a dataset associated with a concept."""
  # Namespace of the dataset.
  namespace: str
  # Name of the dataset.
  name: str
  # Path holding the text to use for negative examples.
  path: Path

  @validator('path')
  def _path_points_to_text_field(cls, path: Path) -> Path:
    if path[-1] == EMBEDDING_KEY:
      raise ValueError(
        f'The path should point to the text field, not its embedding field. Provided path: {path}')
    return path

  num_negative_examples = DEFAULT_NUM_NEG_EXAMPLES


class ExampleOrigin(BaseModel):
  """The origin of an example."""
  # The namespace that holds the dataset.
  dataset_namespace: str

  # The name of the dataset.
  dataset_name: str

  # The id of row in the dataset that the example was added from.
  dataset_row_id: str


DraftId = Union[Literal['main'], str]
DRAFT_MAIN = 'main'


class ExampleIn(BaseModel):
  """An example in a concept without the id (used for adding new examples)."""
  label: bool
  text: Optional[str]
  img: Optional[bytes]
  origin: Optional[ExampleOrigin]
  # The name of the draft to put the example in. If None, puts it in the main draft.
  draft: Optional[DraftId] = DRAFT_MAIN

  @validator('text')
  def parse_text(cls, text: str) -> str:
    """Fixes surrogate errors in text: https://github.com/ijl/orjson/blob/master/README.md#str ."""
    return text.encode('utf-8', 'replace').decode('utf-8')


class Example(ExampleIn):
  """A single example in a concept used for training a concept model."""
  id: str


class Concept(BaseModel):
  """A concept is a collection of examples."""
  # The namespace of the concept.
  namespace: str
  # The name of the concept.
  concept_name: str
  # The type of the data format that this concept represents.
  type: SignalInputType
  data: dict[str, Example]
  version: int = 0

  description: Optional[str] = None

  def drafts(self) -> list[DraftId]:
    """Gets all the drafts for the concept."""
    drafts: set[DraftId] = set([DRAFT_MAIN])  # Always return the main draft.
    for example in self.data.values():
      if example.draft:
        drafts.add(example.draft)
    return list(sorted(drafts))


class OverallScore(str, Enum):
  """Enum holding the overall score."""
  NOT_GOOD = 'not_good'
  OK = 'ok'
  GOOD = 'good'
  VERY_GOOD = 'very_good'
  GREAT = 'great'


def _get_overall_score(f1_score: float) -> OverallScore:
  if f1_score < 0.5:
    return OverallScore.NOT_GOOD
  if f1_score < 0.8:
    return OverallScore.OK
  if f1_score < 0.9:
    return OverallScore.GOOD
  if f1_score < 0.95:
    return OverallScore.VERY_GOOD
  return OverallScore.GREAT


class ConceptMetrics(BaseModel):
  """Metrics for a concept."""
  # The average F1 score for the concept computed using cross validation.
  avg_f1_score: float
  overall_score: OverallScore


@dataclasses.dataclass
class LogisticEmbeddingModel:
  """A model that uses logistic regression with embeddings."""

  version: int = -1

  def __post_init__(self) -> None:
    # See `notebooks/Toxicity.ipynb` for an example of training a concept model.
    self._model = LogisticRegression(
      class_weight=None, C=30, tol=1e-5, warm_start=True, max_iter=1_000, n_jobs=-1)

  def score_embeddings(self, embeddings: np.ndarray) -> np.ndarray:
    """Get the scores for the provided embeddings."""
    try:
      return self._model.predict_proba(embeddings)[:, 1]
    except NotFittedError:
      return np.random.rand(len(embeddings))

  def fit(self, embeddings: np.ndarray, labels: list[bool], sample_weights: list[float]) -> None:
    """Fit the model to the provided embeddings and labels."""
    if len(set(labels)) < 2:
      return
    if len(labels) != len(embeddings):
      raise ValueError(
        f'Length of embeddings ({len(embeddings)}) must match length of labels ({len(labels)})')
    if len(sample_weights) != len(labels):
      raise ValueError(
        f'Length of sample_weights ({len(sample_weights)}) must match length of labels '
        f'({len(labels)})')
    self._model.fit(embeddings, labels, sample_weights)

  def compute_metrics(self, embeddings: np.ndarray, labels: list[bool]) -> ConceptMetrics:
    """Return the concept metrics."""
    fold = KFold(n_splits=3, shuffle=True, random_state=42)
    scores = cross_val_score(self._model, embeddings, labels, scoring='f1', cv=fold, n_jobs=-1)
    avg_f1_score: float = np.mean(scores).item()
    return ConceptMetrics(avg_f1_score=avg_f1_score, overall_score=_get_overall_score(avg_f1_score))


def draft_examples(concept: Concept, draft: DraftId) -> dict[str, Example]:
  """Get the examples in the provided draft by overriding the main draft."""
  draft_examples: dict[str, dict[str, Example]] = {}
  for id, example in concept.data.items():
    draft_examples.setdefault(example.draft or DRAFT_MAIN, {})[example.id] = example

  if draft == DRAFT_MAIN:
    return draft_examples.get(DRAFT_MAIN, {})

  if draft not in draft_examples:
    raise ValueError(
      f'Draft {draft} not found in concept. Found drafts: {list(draft_examples.keys())}')

  # Map the text of the draft to its id so we can dedupe with main.
  draft_text_ids = {example.text: id for id, example in draft_examples[draft].items()}

  # Write each of examples from main to the draft examples only if the text does not appear in the
  # draft.
  for id, example in draft_examples[DRAFT_MAIN].items():
    if example.text not in draft_text_ids:
      draft_examples[draft][id] = example

  return draft_examples[draft]


@dataclasses.dataclass
class ConceptModel:
  """A concept model. Stores all concept model drafts and manages syncing."""
  # The concept that this model is for.
  namespace: str
  concept_name: str

  # The name of the embedding for this model.
  embedding_name: str
  version: int = -1

  column_info: Optional[ConceptColumnInfo] = None

  # The following fields are excluded from JSON serialization, but still pickle-able.
  # Maps a concept id to the embeddings.
  _embeddings: dict[str, np.ndarray] = dataclasses.field(default_factory=dict)
  _logistic_models: dict[DraftId, LogisticEmbeddingModel] = dataclasses.field(default_factory=dict)
  _negative_vectors: Optional[np.ndarray] = None

  def __post_init__(self) -> None:
    if self.column_info:
      self.column_info.path = normalize_path(self.column_info.path)
      self._calibrate_on_dataset(self.column_info)

  def _calibrate_on_dataset(self, column_info: ConceptColumnInfo) -> None:
    """Calibrate the model on the embeddings in the provided vector store."""
    db = get_dataset(column_info.namespace, column_info.name)
    vector_store = db.get_vector_store(self.embedding_name, normalize_path(column_info.path))
    keys = vector_store.keys()
    num_samples = min(column_info.num_negative_examples, len(keys))
    sample_keys = random.sample(keys, num_samples)
    self._negative_vectors = vector_store.get(sample_keys)

  def score_embeddings(self, draft: DraftId, embeddings: np.ndarray) -> np.ndarray:
    """Get the scores for the provided embeddings."""
    return self._get_logistic_model(draft).score_embeddings(embeddings)

  def score(self, draft: DraftId, examples: Iterable[RichData]) -> list[float]:
    """Get the scores for the provided examples."""
    embedding_signal = get_signal_cls(self.embedding_name)()
    if not isinstance(embedding_signal, TextEmbeddingSignal):
      raise ValueError(f'Only text embedding signals are currently supported for concepts. '
                       f'"{self.embedding_name}" is a {type(embedding_signal)}.')

    embed_fn = get_embed_fn(self.embedding_name)
    embeddings = np.array(embed_fn(examples))
    return self._get_logistic_model(draft).score_embeddings(embeddings).tolist()

  def coef(self, draft: DraftId) -> np.ndarray:
    """Get the coefficients of the underlying ML model."""
    return self._get_logistic_model(draft)._model.coef_.reshape(-1)

  def _get_logistic_model(self, draft: DraftId) -> LogisticEmbeddingModel:
    """Get the logistic model for the provided draft."""
    if draft not in self._logistic_models:
      self._logistic_models[draft] = LogisticEmbeddingModel()
    return self._logistic_models[draft]

  def compute_metrics(self, concept: Concept) -> ConceptMetrics:
    """Compute the metrics for the provided concept using the model."""
    examples = draft_examples(concept, DRAFT_MAIN)
    embeddings = np.array([self._embeddings[id] for id in examples.keys()])
    labels = [example.label for example in examples.values()]
    if self._negative_vectors is not None:
      num_implicit_labels = len(self._negative_vectors)
      embeddings = np.concatenate([self._negative_vectors, embeddings])
      labels = [False] * num_implicit_labels + labels
    model = self._get_logistic_model(DRAFT_MAIN)
    return model.compute_metrics(embeddings, labels)

  def sync(self, concept: Concept) -> bool:
    """Update the model with the latest labeled concept data."""
    if concept.version == self.version:
      # The model is up to date.
      return False

    concept_path = (f'{self.namespace}/{self.concept_name}/'
                    f'{self.embedding_name}')
    with DebugTimer(f'Computing embeddings for "{concept_path}"'):
      self._compute_embeddings(concept)

    # Fit each of the drafts, sort by draft name for deterministic behavior.
    for draft in concept.drafts():
      examples = draft_examples(concept, draft)
      embeddings = np.array([self._embeddings[id] for id in examples.keys()])
      labels = [example.label for example in examples.values()]
      num_pos_labels = len([x for x in labels if x])
      num_neg_labels = len([x for x in labels if not x])
      sample_weights = [(1.0 / num_pos_labels if x else 1.0 / num_neg_labels) for x in labels]
      if self._negative_vectors is not None:
        num_implicit_labels = len(self._negative_vectors)
        embeddings = np.concatenate([self._negative_vectors, embeddings])
        labels = [False] * num_implicit_labels + labels
        sample_weights = [1.0 / num_implicit_labels] * num_implicit_labels + sample_weights

      model = self._get_logistic_model(draft)
      with DebugTimer(f'Fitting model for "{concept_path}"'):
        model.fit(embeddings, labels, sample_weights)

      # Synchronize the model version with the concept version.
      model.version = concept.version

    # Synchronize the model version with the concept version.
    self.version = concept.version

    return True

  def _compute_embeddings(self, concept: Concept) -> None:
    embedding_signal = get_signal_cls(self.embedding_name)()
    if not isinstance(embedding_signal, TextEmbeddingSignal):
      raise ValueError(f'Only text embedding signals are currently supported for concepts. '
                       f'"{self.embedding_name}" is a {type(embedding_signal)}.')

    embed_fn = get_embed_fn(self.embedding_name)
    concept_embeddings: dict[str, np.ndarray] = {}

    # Compute the embeddings for the examples with cache miss.
    texts_of_missing_embeddings: dict[str, str] = {}
    for id, example in concept.data.items():
      if id in self._embeddings:
        # Cache hit.
        concept_embeddings[id] = self._embeddings[id]
      else:
        # Cache miss.
        # TODO(smilkov): Support images.
        texts_of_missing_embeddings[id] = example.text or ''

    missing_ids = texts_of_missing_embeddings.keys()
    missing_embeddings = embed_fn(list(texts_of_missing_embeddings.values()))

    for id, embedding in zip(missing_ids, missing_embeddings):
      concept_embeddings[id] = embedding
    self._embeddings = concept_embeddings
