"""The concept database."""

import abc
import os
import pickle
from typing import Optional, cast
from uuid import uuid4

from pydantic import BaseModel

from ..constants import data_path
from ..embeddings.embedding_registry import get_embed_fn
from ..utils import delete_file, file_exists, open_file
from .concept import Concept, ConceptModel, Example, ExampleIn

CONCEPT_JSON_FILENAME = 'concept.json'


class ConceptUpdate(BaseModel):
  """An update to a concept."""
  # List of examples to be inserted.
  insert: Optional[list[ExampleIn]]

  # List of examples to be updated.
  update: Optional[list[Example]]

  # The ids of the examples to be removed.
  remove: Optional[list[str]]


class ConceptDB(abc.ABC):
  """Interface for the concept database."""

  @abc.abstractmethod
  def get(self, namespace: str, name: str) -> Optional[Concept]:
    """Return a concept or None if there isn't one."""
    pass

  @abc.abstractmethod
  def edit(self, namespace: str, name: str, change: ConceptUpdate) -> Concept:
    """Edit a concept."""
    pass

  @abc.abstractmethod
  def remove(self, namespace: str, name: str) -> None:
    """Remove a concept."""
    pass


class ConceptModelDB(abc.ABC):
  """Interface for the concept model database."""

  @abc.abstractmethod
  def get(self, namespace: str, concept_name: str, embedding_name: str) -> Optional[ConceptModel]:
    """Get the model associated with the provided concept and the embedding, or None."""
    pass

  @abc.abstractmethod
  def save(self, concept_model: ConceptModel) -> None:
    """Save the concept model."""
    pass

  @abc.abstractmethod
  def remove(self, namespace: str, concept_name: str, embedding_name: str) -> None:
    """Remove the model of a concept."""
    pass


class DiskConceptModelDB(ConceptModelDB):
  """Interface for the concept model database."""

  def get(self, namespace: str, concept_name: str, embedding_name: str) -> Optional[ConceptModel]:
    """Get the model associated with the provided concept and the embedding."""
    # Make sure the concept exists.
    concept = CONCEPT_DB.get(namespace, concept_name)
    if not concept:
      return None

    # Make sure that the embedding exists.
    if not get_embed_fn(embedding_name):
      raise ValueError(f'Embedding "{embedding_name}" is not registered in the registry.')

    concept_model_path = _concept_model_path(namespace, concept_name, embedding_name)
    if not file_exists(concept_model_path):
      return ConceptModel(namespace=namespace,
                          concept_name=concept_name,
                          embedding_name=embedding_name,
                          embeddings={},
                          version=-1)

    with open_file(concept_model_path, 'rb') as f:
      return pickle.load(f)

  def save(self, model: ConceptModel) -> None:
    """Save the concept model."""
    concept_model_path = _concept_model_path(model.namespace, model.concept_name,
                                             model.embedding_name)
    with open_file(concept_model_path, 'wb') as f:
      pickle.dump(model, f)

  def remove(self, namespace: str, concept_name: str, embedding_name: str) -> None:
    """Remove the model for a concept."""
    concept_model_path = _concept_model_path(namespace, concept_name, embedding_name)

    if not file_exists(concept_model_path):
      raise ValueError(f'Concept model {namespace}/{concept_name}/{embedding_name} does not exist.')

    delete_file(concept_model_path)


def _concept_output_dir(namespace: str, name: str) -> str:
  """Return the output directory for a given concept."""
  return os.path.join(data_path(), 'concept', namespace, name)


def _concept_json_path(namespace: str, name: str) -> str:
  return os.path.join(_concept_output_dir(namespace, name), CONCEPT_JSON_FILENAME)


def _concept_model_path(namespace: str, concept_name: str, embedding_name: str) -> str:
  return os.path.join(_concept_output_dir(namespace, concept_name), f'{embedding_name}.pkl')


class DiskConceptDB(ConceptDB):
  """A concept database."""

  def get(self, namespace: str, name: str) -> Optional[Concept]:
    """Get a concept."""
    concept_json_path = _concept_json_path(namespace, name)

    if not file_exists(concept_json_path):
      return None

    with open_file(concept_json_path) as f:
      return Concept.parse_raw(f.read())

  def edit(self, namespace: str, name: str, change: ConceptUpdate) -> Concept:
    """Edit a concept."""
    concept_json_path = _concept_json_path(namespace, name)

    inserted_points = change.insert or []
    updated_points = change.update or []
    removed_points = change.remove or []

    # Create the concept if it doesn't exist.
    if not file_exists(concept_json_path):
      # Deduce the concept type from the first example.
      points = [*inserted_points, *updated_points]
      if points:
        type = 'text' if points[0].text else 'img'
      else:
        raise ValueError('Cannot create a concept with no examples.')
      concept = Concept(namespace=namespace, concept_name=name, type=type, data=[], version=0)
    else:
      concept = cast(Concept, self.get(namespace, name))

    for example_id in removed_points:
      if example_id not in concept.data:
        raise ValueError(f'Example with id "{example_id}" does not exist.')
      concept.data.pop(example_id)

    for example in inserted_points:
      id = uuid4().hex
      concept.data[id] = Example(id=id, **example.dict())

    for example in updated_points:
      if example.id not in concept.data:
        raise ValueError(f'Example with id "{example.id}" does not exist.')
      # Remove the old example and make a new one with a new id to keep it functional.
      concept.data.pop(example.id)
      concept.data[example.id] = example.copy()

    concept.version += 1

    with open_file(concept_json_path, 'w') as f:
      f.write(concept.json(exclude_none=True))

    return concept

  def remove(self, namespace: str, name: str) -> None:
    """Remove a concept."""
    concept_json_path = _concept_json_path(namespace, name)

    if not file_exists(concept_json_path):
      raise ValueError(f'Concept with namespace "{namespace}" and name "{name}" does not exist.')

    delete_file(concept_json_path)


# A singleton concept database.
CONCEPT_DB = DiskConceptDB()
CONCEPT_MODEL_DB = DiskConceptModelDB()
