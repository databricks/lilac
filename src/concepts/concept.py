"""Defines the concept and the concept models."""
from typing import Iterable, Literal, Optional, Union

import numpy as np
from pydantic import BaseModel
from sklearn import linear_model

from ..embeddings.embedding_registry import get_embed_fn
from ..schema import RichData

LOCAL_CONCEPT_NAMESPACE = 'local'


class ExampleOrigin(BaseModel):
  """The origin of an example."""
  # The namespace that holds the dataset.
  dataset_namespace: str

  # The name of the dataset.
  dataset_name: str

  # The id of row in the dataset that the example was added from.
  dataset_row_id: str


class ExampleIn(BaseModel):
  """An example in a concept without the id (used for adding new examples)."""
  label: bool
  text: Optional[str]
  img: Optional[bytes]
  origin: Optional[ExampleOrigin]


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
  type: Union[Literal['text'], Literal['img']]
  data: dict[str, Example]
  version: int = 0


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
  _embeddings: dict[str, np.ndarray] = {}
  _model: linear_model.LogisticRegression = linear_model.LogisticRegression(solver='liblinear',
                                                                            class_weight='balanced')

  def score_embeddings(self, embeddings: np.ndarray) -> np.ndarray:
    """Get the scores for the provided embeddings."""
    return self._model.predict_proba(embeddings)[:, 1]

  def score(self, examples: Iterable[RichData]) -> list[float]:
    """Get the scores for the provided examples."""
    _, embed_fn = get_embed_fn(self.embedding_name)
    embeddings = embed_fn(examples)
    return self.score_embeddings(embeddings).tolist()

  def sync(self, concept: Concept) -> bool:
    """Update the model with the latest labeled concept data."""
    if concept.version == self.version:
      # The model is up to date.
      return False

    _, embed_fn = get_embed_fn(self.embedding_name)
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

    embedding_matrix = list(concept_embeddings.values())
    new_labels = [concept.data[id].label for id in concept_embeddings.keys()]

    self._model.fit(embedding_matrix, new_labels)
    self._embeddings = concept_embeddings
    # Synchronize the model version with the concept version.
    self.version = concept.version
    return True
