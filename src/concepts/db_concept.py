"""The concept database."""

import abc
import os
import pickle

# NOTE: We have to import the module for uuid so it can be mocked.
import uuid
from typing import List, Optional, Union, cast

from pydantic import BaseModel
from typing_extensions import override

from ..config import data_path
from ..schema import SignalInputType
from ..signals.signal import get_signal_cls
from ..utils import DebugTimer, delete_file, file_exists, open_file
from .concept import DRAFT_MAIN, Concept, ConceptModelManager, DraftId, Example, ExampleIn

CONCEPT_JSON_FILENAME = 'concept.json'


class ConceptInfo(BaseModel):
  """Information about a concept."""
  namespace: str
  name: str
  type: SignalInputType
  drafts: list[DraftId]


class ExampleRemove(BaseModel):
  """An example to be removed from a draft."""
  id: str
  draft: DraftId = DRAFT_MAIN


class ConceptUpdate(BaseModel):
  """An update to a concept."""
  # List of examples to be inserted.
  insert: Optional[list[ExampleIn]] = []

  # List of examples to be updated.
  update: Optional[list[Example]] = []

  # The ids of the examples to be removed.
  remove: Optional[list[ExampleRemove]] = []


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
  def create(self, namespace: str, name: str, type: SignalInputType) -> Concept:
    """Create a concept."""
    pass

  @abc.abstractmethod
  def edit(self, namespace: str, name: str, change: ConceptUpdate) -> Concept:
    """Edit a concept. If the concept doesn't exist, throw an error."""
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
  def get(self, namespace: str, concept_name: str, embedding_name: str) -> ConceptModelManager:
    """Get the manager associated with the provided concept the embedding."""
    pass

  @abc.abstractmethod
  def _save(self, manager: ConceptModelManager) -> None:
    """Save the concept model manager."""
    pass

  def in_sync(self, manager: ConceptModelManager) -> bool:
    """Return True if the manager is up to date with the concept."""
    concept = self._concept_db.get(manager.namespace, manager.concept_name)
    if not concept:
      raise ValueError(f'Concept "{manager.namespace}/{manager.concept_name}" does not exist.')
    return concept.version == manager.version

  def sync(self, manager: ConceptModelManager) -> bool:
    """Sync the concept model. Returns true if the model was updated."""
    concept = self._concept_db.get(manager.namespace, manager.concept_name)
    if not concept:
      raise ValueError(f'Concept "{manager.namespace}/{manager.concept_name}" does not exist.')
    concept_path = (f'{manager.namespace}/{manager.concept_name}/'
                    f'{manager.embedding_name}')
    with DebugTimer(f'Syncing concept model "{concept_path}"'):
      model_updated = manager.sync(concept)
    self._save(manager)
    return model_updated

  @abc.abstractmethod
  def remove(self, namespace: str, concept_name: str, embedding_name: str) -> None:
    """Remove the model of a concept."""
    pass


class DiskConceptModelDB(ConceptModelDB):
  """Interface for the concept model database."""

  @override
  def get(self, namespace: str, concept_name: str, embedding_name: str) -> ConceptModelManager:
    # Make sure the concept exists.
    concept = self._concept_db.get(namespace, concept_name)
    if not concept:
      raise ValueError(f'Concept "{namespace}/{concept_name}" does not exist.')

    # Make sure that the embedding signal exists.
    if not get_signal_cls(embedding_name):
      raise ValueError(f'Embedding signal "{embedding_name}" not found in the registry.')

    concept_model_path = _concept_model_path(namespace, concept_name, embedding_name)
    if not file_exists(concept_model_path):
      return ConceptModelManager(
        namespace=namespace, concept_name=concept_name, embedding_name=embedding_name, version=-1)

    with open_file(concept_model_path, 'rb') as f:
      return pickle.load(f)

  def _save(self, manager: ConceptModelManager) -> None:
    """Save the concept model."""
    concept_model_path = _concept_model_path(manager.namespace, manager.concept_name,
                                             manager.embedding_name)
    with open_file(concept_model_path, 'wb') as f:
      pickle.dump(manager, f)

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
              type=SignalInputType.TEXT,
              # TODO: list the drafts.
              drafts=[DRAFT_MAIN]))

    return concept_infos

  @override
  def get(self, namespace: str, name: str) -> Optional[Concept]:
    concept_json_path = _concept_json_path(namespace, name)

    if not file_exists(concept_json_path):
      return None

    with open_file(concept_json_path) as f:
      return Concept.parse_raw(f.read())

  @override
  def create(self, namespace: str, name: str, type: SignalInputType) -> Concept:
    """Create a concept."""
    concept_json_path = _concept_json_path(namespace, name)
    if file_exists(concept_json_path):
      raise ValueError(f'Concept with namespace "{namespace}" and name "{name}" already exists.')

    concept = Concept(namespace=namespace, concept_name=name, type=type, data={}, version=0)
    with open_file(concept_json_path, 'w') as f:
      f.write(concept.json(exclude_none=True))

    return concept

  def _validate_examples(self, examples: List[Union[ExampleIn, Example]],
                         type: SignalInputType) -> None:
    for example in examples:
      inferred_type = 'text' if example.text else 'img'
      if inferred_type != type:
        raise ValueError(f'Example type "{inferred_type}" does not match concept type "{type}".')

  @override
  def edit(self, namespace: str, name: str, change: ConceptUpdate) -> Concept:
    concept_json_path = _concept_json_path(namespace, name)

    if not file_exists(concept_json_path):
      raise ValueError(f'Concept with namespace "{namespace}" and name "{name}" does not exist. '
                       'Please call create() first.')

    inserted_points = change.insert or []
    updated_points = change.update or []
    removed_points = change.remove or []

    concept = cast(Concept, self.get(namespace, name))

    self._validate_examples([*inserted_points, *updated_points], concept.type)

    for remove_example in removed_points:
      if remove_example.id not in concept.data[remove_example.draft]:
        raise ValueError(
          f'Example with id "{remove_example.id}" and draft "{remove_example.draft}" '
          'does not exist.')
      concept.data[remove_example.draft].pop(remove_example.id)

    for example in inserted_points:
      id = uuid.uuid4().hex
      concept.data.setdefault(example.draft, {})[id] = Example(id=id, **example.dict())

    for example in updated_points:
      if example.id not in concept.data[example.draft]:
        raise ValueError(f'Example with id "{example.id}" and draft "{example.draft}" '
                         'does not exist.')
      # Remove the old example and make a new one with a new id to keep it functional.
      concept.data[example.draft].pop(example.id)
      concept.data[example.draft][example.id] = example.copy()

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
