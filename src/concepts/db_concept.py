"""The concept database."""

import abc
import os
import pickle
from typing import Optional, cast
from uuid import uuid4

from pydantic import BaseModel
from typing_extensions import override

from ..config import data_path
from ..embeddings.embedding_registry import get_embedding_cls
from ..schema import EnrichmentType
from ..utils import DebugTimer, delete_file, file_exists, open_file
from .concept import Concept, ConceptModel, Example, ExampleIn

CONCEPT_JSON_FILENAME = 'concept.json'


class ConceptInfo(BaseModel):
  """Information about a concept."""
  namespace: str
  name: str
  enrichment_type: EnrichmentType


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
  def list(self) -> list[ConceptInfo]:
    """List all the concepts."""
    pass

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

  _concept_db: ConceptDB

  def __init__(self, concept_db: ConceptDB) -> None:
    self._concept_db = concept_db

  @abc.abstractmethod
  def get(self, namespace: str, concept_name: str, embedding_name: str) -> ConceptModel:
    """Get the model associated with the provided concept and the embedding."""
    pass

  @abc.abstractmethod
  def _save(self, concept_model: ConceptModel) -> None:
    """Save the concept model."""
    pass

  def in_sync(self, concept_model: ConceptModel) -> bool:
    """Return True if the model is up to date with the concept."""
    concept = self._concept_db.get(concept_model.namespace, concept_model.concept_name)
    if not concept:
      raise ValueError(
          f'Concept "{concept_model.namespace}/{concept_model.concept_name}" does not exist.')
    return concept.version == concept_model.version

  def sync(self, concept_model: ConceptModel) -> bool:
    """Sync the concept model. Returns true if the model was updated."""
    concept = self._concept_db.get(concept_model.namespace, concept_model.concept_name)
    if not concept:
      raise ValueError(
          f'Concept "{concept_model.namespace}/{concept_model.concept_name}" does not exist.')
    concept_path = (f'{concept_model.namespace}/{concept_model.concept_name}/'
                    f'{concept_model.embedding_name}')
    with DebugTimer(f'Syncing concept model "{concept_path}"'):
      model_updated = concept_model.sync(concept)
    self._save(concept_model)
    return model_updated

  @abc.abstractmethod
  def remove(self, namespace: str, concept_name: str, embedding_name: str) -> None:
    """Remove the model of a concept."""
    pass


class DiskConceptModelDB(ConceptModelDB):
  """Interface for the concept model database."""

  @override
  def get(self, namespace: str, concept_name: str, embedding_name: str) -> ConceptModel:
    # Make sure the concept exists.
    concept = self._concept_db.get(namespace, concept_name)
    if not concept:
      raise ValueError(f'Concept "{namespace}/{concept_name}" does not exist.')

    # Make sure that the embedding exists.
    if not get_embedding_cls(embedding_name):
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

  def _save(self, model: ConceptModel) -> None:
    """Save the concept model."""
    concept_model_path = _concept_model_path(model.namespace, model.concept_name,
                                             model.embedding_name)
    with open_file(concept_model_path, 'wb') as f:
      pickle.dump(model, f)

  @override
  def remove(self, namespace: str, concept_name: str, embedding_name: str) -> None:
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

  @override
  def list(self) -> list[ConceptInfo]:
    # Read the concepts and return a ConceptInfo containing the namespace and name.
    concept_infos = []
    for root, _, files in os.walk(data_path()):
      for file in files:
        if file == CONCEPT_JSON_FILENAME:
          namespace, name = root.split('/')[-2:]
          concept_infos.append(
              ConceptInfo(
                  namespace=namespace,
                  name=name,
                  # TODO(nsthorat): Generalize this to images.
                  enrichment_type=EnrichmentType.TEXT))

    return concept_infos

  @override
  def get(self, namespace: str, name: str) -> Optional[Concept]:
    concept_json_path = _concept_json_path(namespace, name)

    if not file_exists(concept_json_path):
      return None

    with open_file(concept_json_path) as f:
      return Concept.parse_raw(f.read())

  @override
  def edit(self, namespace: str, name: str, change: ConceptUpdate) -> Concept:
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

  @override
  def remove(self, namespace: str, name: str) -> None:
    concept_json_path = _concept_json_path(namespace, name)

    if not file_exists(concept_json_path):
      raise ValueError(f'Concept with namespace "{namespace}" and name "{name}" does not exist.')

    delete_file(concept_json_path)


# A singleton concept database.
DISK_CONCEPT_DB = DiskConceptDB()
DISK_CONCEPT_MODEL_DB = DiskConceptModelDB(DISK_CONCEPT_DB)
