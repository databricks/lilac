"""Defines the concept and the concept models."""
import dataclasses
import random
from enum import Enum
from typing import Callable, Literal, Optional, Union

import numpy as np
from joblib import Parallel, delayed
from pydantic import BaseModel, validator
from scipy.interpolate import interp1d
from sklearn.base import clone
from sklearn.exceptions import NotFittedError
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import precision_recall_curve, roc_auc_score
from sklearn.model_selection import KFold

from ..db_manager import get_dataset
from ..embeddings.embedding import get_embed_fn
from ..schema import EMBEDDING_KEY, Path, SignalInputType, normalize_path
from ..signals.signal import TextEmbeddingSignal, get_signal_cls
from ..utils import DebugTimer

LOCAL_CONCEPT_NAMESPACE = 'local'

# Number of randomly sampled negative examples to use for training. This is used to obtain a more
# balanced model that works with a specific dataset.
DEFAULT_NUM_NEG_EXAMPLES = 100

# The maximum number of cross-validation models to train.
MAX_NUM_CROSS_VAL_MODELS = 15
# The β weight to use for the F-beta score: https://scikit-learn.org/stable/modules/generated/sklearn.metrics.fbeta_score.html
# β = 0.5 means we value precision 2x as much as recall.
# β = 2 means we value recall 2x as much as precision.
F_BETA_WEIGHT = 0.5


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
  text: Optional[str] = None
  img: Optional[bytes] = None
  origin: Optional[ExampleOrigin] = None
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
  f1: float
  precision: float
  recall: float
  roc_auc: float
  overall: OverallScore


@dataclasses.dataclass
class LogisticEmbeddingModel:
  """A model that uses logistic regression with embeddings."""

  _metrics: Optional[ConceptMetrics] = None
  _threshold: float = 0.5

  def __post_init__(self) -> None:
    # See `notebooks/Toxicity.ipynb` for an example of training a concept model.
    self._model = LogisticRegression(
      class_weight=None, C=30, tol=1e-5, warm_start=True, max_iter=5_000, n_jobs=-1)

  def score_embeddings(self, embeddings: np.ndarray) -> np.ndarray:
    """Get the scores for the provided embeddings."""
    try:
      y_probs = self._model.predict_proba(embeddings)[:, 1]
      # Map [0, threshold, 1] to [0, 0.5, 1].
      interpolate_fn = interp1d([0, self._threshold, 1], [0, 0.4999, 1])
      return interpolate_fn(y_probs)
    except NotFittedError:
      return np.random.rand(len(embeddings))

  def _setup_training(
      self, X_train: np.ndarray, labels: Union[list[bool], np.ndarray],
      implicit_negatives: Optional[np.ndarray]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    num_pos_labels = len([y for y in labels if y])
    num_neg_labels = len([y for y in labels if not y])
    sample_weights = [(1.0 / num_pos_labels if y else 1.0 / num_neg_labels) for y in labels]
    y_train = np.array(labels)

    if implicit_negatives is not None:
      num_implicit_labels = len(implicit_negatives)
      implicit_labels = np.array([False] * num_implicit_labels)
      X_train = np.concatenate([implicit_negatives, X_train])
      y_train = np.concatenate([implicit_labels, y_train])
      sample_weights = [1.0 / num_implicit_labels] * num_implicit_labels + sample_weights

    # Normalize sample weights to sum to the number of training examples.
    weights = np.array(sample_weights)
    weights *= (X_train.shape[0] / np.sum(weights))

    # Shuffle the data in unison.
    p = np.random.permutation(len(X_train))
    X_train = X_train[p]
    y_train = y_train[p]
    weights = weights[p]

    return X_train, y_train, weights

  def fit(self, embeddings: np.ndarray, labels: list[bool],
          implicit_negatives: Optional[np.ndarray]) -> None:
    """Fit the model to the provided embeddings and labels."""
    label_set = set(labels)
    if implicit_negatives is not None:
      label_set.add(False)
    if len(label_set) < 2:
      return
    if len(labels) != len(embeddings):
      raise ValueError(
        f'Length of embeddings ({len(embeddings)}) must match length of labels ({len(labels)})')
    X_train, y_train, sample_weights = self._setup_training(embeddings, labels, implicit_negatives)
    self._model.fit(X_train, y_train, sample_weights)
    self._metrics, self._threshold = self._compute_metrics(embeddings, labels, implicit_negatives)

  def _compute_metrics(
      self, embeddings: np.ndarray, labels: list[bool],
      implicit_negatives: Optional[np.ndarray]) -> tuple[Optional[ConceptMetrics], float]:
    """Return the concept metrics."""
    labels_np = np.array(labels)
    n_splits = min(len(labels_np), MAX_NUM_CROSS_VAL_MODELS)
    fold = KFold(n_splits, shuffle=True, random_state=42)

    def _fit_and_score(model: LogisticRegression, X_train: np.ndarray, y_train: np.ndarray,
                       sample_weights: np.ndarray, X_test: np.ndarray,
                       y_test: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
      if len(set(y_train)) < 2:
        return np.array([]), np.array([])
      model.fit(X_train, y_train, sample_weights)
      y_pred = model.predict_proba(X_test)[:, 1]
      return y_test, y_pred

    # Compute the metrics for each validation fold in parallel.
    jobs: list[Callable] = []
    for (train_index, test_index) in fold.split(embeddings):
      X_train, y_train = embeddings[train_index], labels_np[train_index]
      X_train, y_train, sample_weights = self._setup_training(X_train, y_train, implicit_negatives)
      X_test, y_test = embeddings[test_index], labels_np[test_index]
      model = clone(self._model)
      jobs.append(delayed(_fit_and_score)(model, X_train, y_train, sample_weights, X_test, y_test))
    results = Parallel(n_jobs=-1)(jobs)

    y_test = np.concatenate([y_test for y_test, _ in results], axis=0)
    y_pred = np.concatenate([y_pred for _, y_pred in results], axis=0)
    if len(set(y_test)) < 2:
      return None, 0.5
    roc_auc_val = roc_auc_score(y_test, y_pred)
    precision, recall, thresholds = precision_recall_curve(y_test, y_pred)
    numerator = (1 + F_BETA_WEIGHT**2) * precision * recall
    denom = (F_BETA_WEIGHT**2 * precision) + recall
    f1_scores = np.divide(numerator, denom, out=np.zeros_like(denom), where=(denom != 0))
    max_f1: float = np.max(f1_scores)
    max_f1_index = np.argmax(f1_scores)
    max_f1_thresh: float = thresholds[max_f1_index]
    max_f1_prec: float = precision[max_f1_index]
    max_f1_recall: float = recall[max_f1_index]
    metrics = ConceptMetrics(
      f1=max_f1,
      precision=max_f1_prec,
      recall=max_f1_recall,
      roc_auc=float(roc_auc_val),
      overall=_get_overall_score(max_f1))
    return metrics, max_f1_thresh


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

  batch_size = 4096

  column_info: Optional[ConceptColumnInfo] = None

  # The following fields are excluded from JSON serialization, but still pickle-able.
  # Maps a concept id to the embeddings.
  _embeddings: dict[str, np.ndarray] = dataclasses.field(default_factory=dict)
  _logistic_models: dict[DraftId, LogisticEmbeddingModel] = dataclasses.field(default_factory=dict)
  _negative_vectors: Optional[np.ndarray] = None

  def get_metrics(self, concept: Concept) -> Optional[ConceptMetrics]:
    """Return the metrics for this model."""
    return self._get_logistic_model(DRAFT_MAIN)._metrics

  def __post_init__(self) -> None:
    if self.column_info:
      self.column_info.path = normalize_path(self.column_info.path)
      self._calibrate_on_dataset(self.column_info)

  def _calibrate_on_dataset(self, column_info: ConceptColumnInfo) -> None:
    """Calibrate the model on the embeddings in the provided vector store."""
    db = get_dataset(column_info.namespace, column_info.name)
    vector_index = db.get_vector_db_index(self.embedding_name, normalize_path(column_info.path))
    vector_store = vector_index.get_vector_store()
    keys = vector_store.keys()
    num_samples = min(column_info.num_negative_examples, len(keys))
    sample_keys = random.sample(keys, num_samples)
    self._negative_vectors = vector_store.get(sample_keys)

  def score_embeddings(self, draft: DraftId, embeddings: np.ndarray) -> np.ndarray:
    """Get the scores for the provided embeddings."""
    return self._get_logistic_model(draft).score_embeddings(embeddings)

  def coef(self, draft: DraftId) -> np.ndarray:
    """Get the coefficients of the underlying ML model."""
    return self._get_logistic_model(draft)._model.coef_.reshape(-1)

  def _get_logistic_model(self, draft: DraftId) -> LogisticEmbeddingModel:
    """Get the logistic model for the provided draft."""
    if draft not in self._logistic_models:
      self._logistic_models[draft] = LogisticEmbeddingModel()
    return self._logistic_models[draft]

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
      model = self._get_logistic_model(draft)
      with DebugTimer(f'Fitting model for "{concept_path}"'):
        model.fit(embeddings, labels, self._negative_vectors)

    # Synchronize the model version with the concept version.
    self.version = concept.version

    return True

  def _compute_embeddings(self, concept: Concept) -> None:
    signal_cls = get_signal_cls(self.embedding_name)
    if not signal_cls:
      raise ValueError(f'Embedding signal "{self.embedding_name}" not found in the registry.')
    embedding_signal = signal_cls()
    if not isinstance(embedding_signal, TextEmbeddingSignal):
      raise ValueError(f'Only text embedding signals are currently supported for concepts. '
                       f'"{self.embedding_name}" is a {type(embedding_signal)}.')

    embed_fn = get_embed_fn(self.embedding_name, split=False)
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

    for id, (embedding,) in zip(missing_ids, missing_embeddings):
      concept_embeddings[id] = embedding['vector']
    self._embeddings = concept_embeddings
