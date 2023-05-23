"""Defines the concept and the concept models."""
from typing import Any, Iterable, Literal, Optional, Union

import numpy as np
from pydantic import BaseModel
from sklearn.linear_model import LogisticRegression

from ..embeddings.embedding import get_embed_fn
from ..schema import RichData, SignalInputType
from ..signals.signal import TextEmbeddingSignal, get_signal_cls
from ..utils import DebugTimer

LOCAL_CONCEPT_NAMESPACE = 'local'


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


class Example(ExampleIn):
  """A single example in a concept used for training a concept model."""
  id: str


class Concept(BaseModel):
  """A concept is a collection of examples."""
  # The namespace of the concept.
  namespace: str = LOCAL_CONCEPT_NAMESPACE
  # The name of the concept.
  concept_name: str
  # The type of the data format that this concept represents.
  type: SignalInputType
  data: dict[str, Example]
  version: int = 0

  def drafts(self) -> list[DraftId]:
    """Gets all the drafts for the concept."""
    drafts: set[DraftId] = set([DRAFT_MAIN])  # Always return the main draft.
    for example in self.data.values():
      if example.draft:
        drafts.add(example.draft)
    return list(sorted(drafts))


class ConceptModel(BaseModel):
  """A concept model."""

  class Config:
    arbitrary_types_allowed = True
    underscore_attrs_are_private = True

  # The concept that this model is for.
  namespace: str
  concept_name: str

  # The name of the embedding for this model.
  embedding_name: str
  version: int = -1

  # The following fields are excluded from JSON serialization, but still pickleable.
  # See `notebooks/Toxicity.ipynb` for an example of training a concept model.
  _model: LogisticRegression = LogisticRegression(
    class_weight='balanced', C=30, tol=1e-5, warm_start=True, max_iter=1_000, n_jobs=-1)

  def score_embeddings(self, embeddings: np.ndarray) -> np.ndarray:
    """Get the scores for the provided embeddings."""
    return self._model.predict_proba(embeddings)[:, 1]

  def score(self, examples: Iterable[RichData]) -> list[float]:
    """Get the scores for the provided examples."""
    embedding_signal = get_signal_cls(self.embedding_name)()
    if not isinstance(embedding_signal, TextEmbeddingSignal):
      raise ValueError(f'Only text embedding signals are currently supported for concepts. '
                       f'"{self.embedding_name}" is a {type(embedding_signal)}.')

    embed_fn = get_embed_fn(embedding_signal)

    embeddings = np.array(embed_fn(examples))
    return self.score_embeddings(embeddings).tolist()

  def fit(self, embeddings: np.ndarray, labels: list[bool]) -> None:
    """Fit the model to the provided embeddings and labels."""
    self._model.fit(embeddings, labels)


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

  # Map the text of the draft to its id so we can dedup with main.
  draft_text_ids = {example.text: id for id, example in draft_examples[draft].items()}

  # Write each of examples from main to the draft examples only if the text does not appear in the
  # draft.
  for id, example in draft_examples[DRAFT_MAIN].items():
    if example.text not in draft_text_ids:
      draft_examples[draft][id] = example

  return draft_examples[draft]


class ConceptModelManager(BaseModel):
  """A concept model. Stores all concept model drafts and manages syncing."""
  # The concept that this model is for.
  namespace: str
  concept_name: str

  # The name of the embedding for this model.
  embedding_name: str
  version: int = -1

  class Config:
    arbitrary_types_allowed = True
    underscore_attrs_are_private = True

  # The following fields are excluded from JSON serialization, but still pickleable.
  # Maps a concept id to the embeddings.
  _embeddings: dict[str, np.ndarray] = {}
  _concept_models: dict[DraftId, ConceptModel] = {}

  def __init__(self,
               concept_models: Optional[dict[DraftId, ConceptModel]] = {},
               **kwargs: Any) -> None:

    super().__init__(**kwargs)
    if concept_models:
      self._concept_models = concept_models

  def get_model(self, draft: DraftId) -> ConceptModel:
    """Get the model for the provided draft."""
    if draft not in self._concept_models:
      self._concept_models[draft] = ConceptModel(
        namespace=self.namespace,
        concept_name=self.concept_name,
        embedding_name=self.embedding_name,
        version=-1)
    return self._concept_models[draft]

  def sync(self, concept: Concept) -> bool:
    """Update the model with the latest labeled concept data."""
    if concept.version == self.version:
      # The model is up to date.
      return False

    self._compute_embeddings(concept)
    self._fit_drafts(concept)

    # Synchronize the model version with the concept version.
    self.version = concept.version

    return True

  def _fit_drafts(self, concept: Concept) -> None:
    # Fit each of the drafts, sort by draft name for deterministic behavior.
    for draft in concept.drafts():
      examples = draft_examples(concept, draft)
      embeddings = np.array([self._embeddings[id] for id in examples.keys()])
      labels = [example.label for example in examples.values()]

      model = self.get_model(draft)
      model.fit(embeddings, labels)

      # Synchronize the model version with the concept version.
      model.version = concept.version

  def _compute_embeddings(self, concept: Concept) -> None:
    embedding_signal = get_signal_cls(self.embedding_name)()
    if not isinstance(embedding_signal, TextEmbeddingSignal):
      raise ValueError(f'Only text embedding signals are currently supported for concepts. '
                       f'"{self.embedding_name}" is a {type(embedding_signal)}.')

    embed_fn = get_embed_fn(embedding_signal)
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
    with DebugTimer('Computing embeddings for examples in concept '
                    f'"{self.namespace}/{self.concept_name}/{self.embedding_name}"'):
      missing_embeddings = embed_fn(list(texts_of_missing_embeddings.values()))

    for id, embedding in zip(missing_ids, missing_embeddings):
      concept_embeddings[id] = embedding
    self._embeddings = concept_embeddings
