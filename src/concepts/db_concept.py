"""The concept database."""

import abc
import glob
import json
import os
import pickle
import shutil

# NOTE: We have to import the module for uuid so it can be mocked.
import uuid
from pathlib import Path
from typing import List, Optional, Union, cast

from pydantic import BaseModel
from pyparsing import Any
from typing_extensions import override

from ..config import data_path
from ..schema import PATH_WILDCARD, SignalInputType, normalize_path
from ..signals.signal import get_signal_cls
from ..utils import DATASETS_DIR_NAME, delete_file, file_exists, get_dataset_output_dir, open_file
from .concept import (
  DRAFT_MAIN,
  Concept,
  ConceptColumnInfo,
  ConceptModel,
  DraftId,
  Example,
  ExampleIn,
)

DATASET_CONCEPTS_DIR = '.concepts'
CONCEPT_JSON_FILENAME = 'concept.json'


class ConceptInfo(BaseModel):
  """Information about a concept."""
  namespace: str
  name: str
  type: SignalInputType
  drafts: list[DraftId]


class ConceptUpdate(BaseModel):
  """An update to a concept."""
  # List of examples to be inserted.
  insert: Optional[list[ExampleIn]] = []

  # List of examples to be updated.
  update: Optional[list[Example]] = []

  # The ids of the examples to be removed.
  remove: Optional[list[str]] = []


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
  def create(self,
             namespace: str,
             name: str,
             type: SignalInputType,
             description: Optional[str] = None) -> Concept:
    """Create a concept.

    Args:
      namespace: The namespace of the concept.
      name: The name of the concept.
      type: The input type of the concept.
      description: The description of the concept.
    """
    pass

  @abc.abstractmethod
  def edit(self, namespace: str, name: str, change: ConceptUpdate) -> Concept:
    """Edit a concept. If the concept doesn't exist, throw an error."""
    pass

  @abc.abstractmethod
  def remove(self, namespace: str, name: str) -> None:
    """Remove a concept."""
    pass

  @abc.abstractmethod
  def merge_draft(self, namespace: str, name: str, draft: DraftId) -> Concept:
    """Merge a draft concept.."""
    pass


class ConceptModelDB(abc.ABC):
  """Interface for the concept model database."""

  _concept_db: ConceptDB

  def __init__(self, concept_db: ConceptDB) -> None:
    self._concept_db = concept_db

  @abc.abstractmethod
  def create(self,
             namespace: str,
             concept_name: str,
             embedding_name: str,
             column_info: Optional[ConceptColumnInfo] = None) -> ConceptModel:
    """Create the concept model."""
    pass

  @abc.abstractmethod
  def get(self,
          namespace: str,
          concept_name: str,
          embedding_name: str,
          column_info: Optional[ConceptColumnInfo] = None) -> Optional[ConceptModel]:
    """Get the model associated with the provided concept the embedding.

    Returns None if the model does not exist.
    """
    pass

  @abc.abstractmethod
  def _save(self, model: ConceptModel, column_info: Optional[ConceptColumnInfo]) -> None:
    """Save the concept model."""
    pass

  def in_sync(self, model: ConceptModel) -> bool:
    """Return True if the model is up to date with the concept."""
    concept = self._concept_db.get(model.namespace, model.concept_name)
    if not concept:
      raise ValueError(f'Concept "{model.namespace}/{model.concept_name}" does not exist.')
    return concept.version == model.version

  def sync(self, model: ConceptModel, column_info: Optional[ConceptColumnInfo]) -> bool:
    """Sync the concept model. Returns true if the model was updated."""
    concept = self._concept_db.get(model.namespace, model.concept_name)
    if not concept:
      raise ValueError(f'Concept "{model.namespace}/{model.concept_name}" does not exist.')
    model_updated = model.sync(concept)
    self._save(model, column_info)
    return model_updated

  @abc.abstractmethod
  def remove(self,
             namespace: str,
             concept_name: str,
             embedding_name: str,
             column_info: Optional[ConceptColumnInfo] = None) -> None:
    """Remove the model of a concept."""
    pass

  @abc.abstractmethod
  def remove_all(self, namespace: str, concept_name: str) -> None:
    """Remove all the models associated with a concept."""
    pass

  @abc.abstractmethod
  def get_column_infos(self, namespace: str, concept_name: str) -> list[ConceptColumnInfo]:
    """Get the dataset columns where this concept was applied to."""
    pass


class DiskConceptModelDB(ConceptModelDB):
  """Interface for the concept model database."""

  @override
  def create(self,
             namespace: str,
             concept_name: str,
             embedding_name: str,
             column_info: Optional[ConceptColumnInfo] = None) -> ConceptModel:
    if self.get(namespace, concept_name, embedding_name, column_info):
      raise ValueError('Concept model already exists.')

    return ConceptModel(
      namespace=namespace,
      concept_name=concept_name,
      embedding_name=embedding_name,
      version=-1,
      column_info=column_info)

  @override
  def get(self,
          namespace: str,
          concept_name: str,
          embedding_name: str,
          column_info: Optional[ConceptColumnInfo] = None) -> Optional[ConceptModel]:
    # Make sure the concept exists.
    concept = self._concept_db.get(namespace, concept_name)
    if not concept:
      raise ValueError(f'Concept "{namespace}/{concept_name}" does not exist.')

    # Make sure that the embedding signal exists.
    if not get_signal_cls(embedding_name):
      raise ValueError(f'Embedding signal "{embedding_name}" not found in the registry.')

    concept_model_path = _concept_model_path(namespace, concept_name, embedding_name, column_info)
    if not file_exists(concept_model_path):
      return None

    with open_file(concept_model_path, 'rb') as f:
      return pickle.load(f)

  def _save(self, model: ConceptModel, column_info: Optional[ConceptColumnInfo]) -> None:
    """Save the concept model."""
    concept_model_path = _concept_model_path(model.namespace, model.concept_name,
                                             model.embedding_name, column_info)
    with open_file(concept_model_path, 'wb') as f:
      pickle.dump(model, f)

  @override
  def remove(self,
             namespace: str,
             concept_name: str,
             embedding_name: str,
             column_info: Optional[ConceptColumnInfo] = None) -> None:
    concept_model_path = _concept_model_path(namespace, concept_name, embedding_name, column_info)

    if not file_exists(concept_model_path):
      raise ValueError(f'Concept model {namespace}/{concept_name}/{embedding_name} does not exist.')

    delete_file(concept_model_path)

  @override
  def remove_all(self, namespace: str, concept_name: str) -> None:
    datasets_path = os.path.join(data_path(), DATASETS_DIR_NAME)
    # Skip if 'datasets' doesn't exist.
    if not os.path.isdir(datasets_path):
      return

    dirs = glob.iglob(
      os.path.join(datasets_path, '**', DATASET_CONCEPTS_DIR, namespace, concept_name),
      recursive=True)
    for dir in dirs:
      shutil.rmtree(dir, ignore_errors=True)

  @override
  def get_column_infos(self, namespace: str, concept_name: str) -> list[ConceptColumnInfo]:
    datasets_path = os.path.join(data_path(), DATASETS_DIR_NAME)
    # Skip if 'datasets' doesn't exist.
    if not os.path.isdir(datasets_path):
      return []

    dirs = glob.iglob(
      os.path.join(datasets_path, '**', DATASET_CONCEPTS_DIR, namespace, concept_name),
      recursive=True)
    result: list[ConceptColumnInfo] = []
    for dir in dirs:
      dir = os.path.relpath(dir, datasets_path)
      dataset_namespace, dataset_name, *path, _, _, _ = Path(dir).parts
      result.append(ConceptColumnInfo(namespace=dataset_namespace, name=dataset_name, path=path))
    return result


def _concept_output_dir(namespace: str, name: str) -> str:
  """Return the output directory for a given concept."""
  return os.path.join(data_path(), 'concept', namespace, name)


def _concept_json_path(namespace: str, name: str) -> str:
  return os.path.join(_concept_output_dir(namespace, name), CONCEPT_JSON_FILENAME)


def _concept_model_path(namespace: str,
                        concept_name: str,
                        embedding_name: str,
                        column_info: Optional[ConceptColumnInfo] = None) -> str:
  if not column_info:
    return os.path.join(_concept_output_dir(namespace, concept_name), f'{embedding_name}.pkl')

  dataset_dir = get_dataset_output_dir(data_path(), column_info.namespace, column_info.name)
  path_tuple = normalize_path(column_info.path)
  path_without_wildcards = (p for p in path_tuple if p != PATH_WILDCARD)
  path_dir = os.path.join(dataset_dir, *path_without_wildcards)
  return os.path.join(path_dir, DATASET_CONCEPTS_DIR, namespace, concept_name,
                      f'{embedding_name}.pkl')


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
          concept = cast(Concept, self.get(namespace, name))

          concept_infos.append(
            ConceptInfo(
              namespace=namespace,
              name=name,
              # TODO(nsthorat): Generalize this to images.
              type=SignalInputType.TEXT,
              drafts=concept.drafts()))

    return concept_infos

  @override
  def get(self, namespace: str, name: str) -> Optional[Concept]:
    concept_json_path = _concept_json_path(namespace, name)

    if not file_exists(concept_json_path):
      return None

    with open_file(concept_json_path) as f:
      obj: dict[str, Any] = json.load(f)
      if 'namespace' not in obj:
        obj['namespace'] = namespace
      return Concept.parse_obj(obj)

  @override
  def create(self,
             namespace: str,
             name: str,
             type: SignalInputType,
             description: Optional[str] = None) -> Concept:
    """Create a concept."""
    concept_json_path = _concept_json_path(namespace, name)
    if file_exists(concept_json_path):
      raise ValueError(f'Concept with namespace "{namespace}" and name "{name}" already exists.')

    concept = Concept(
      namespace=namespace,
      concept_name=name,
      type=type,
      data={},
      version=0,
      description=description)
    self._save(concept)
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
      if remove_example not in concept.data:
        raise ValueError(f'Example with id "{remove_example}" does not exist.')
      concept.data.pop(remove_example)

    for example in inserted_points:
      id = uuid.uuid4().hex
      concept.data[id] = Example(id=id, **example.dict())

    for example in updated_points:
      if example.id not in concept.data:
        raise ValueError(f'Example with id "{example.id}" does not exist.')

      # Remove the old example and make a new one with a new id to keep it functional.
      concept.data.pop(example.id)
      concept.data[example.id] = example.copy()

    concept.version += 1

    self._save(concept)

    return concept

  def _save(self, concept: Concept) -> None:
    concept_json_path = _concept_json_path(concept.namespace, concept.concept_name)

    with open_file(concept_json_path, 'w') as f:
      f.write(concept.json(exclude_none=True, indent=2, exclude_defaults=True))

  @override
  def remove(self, namespace: str, name: str) -> None:
    concept_dir = _concept_output_dir(namespace, name)

    if not file_exists(concept_dir):
      raise ValueError(f'Concept with namespace "{namespace}" and name "{name}" does not exist.')

    shutil.rmtree(concept_dir, ignore_errors=True)

  @override
  def merge_draft(self, namespace: str, name: str, draft: DraftId) -> Concept:
    """Merge a draft concept.."""
    concept = self.get(namespace, name)
    if not concept:
      raise ValueError(f'Concept with namespace "{namespace}" and name "{name}" does not exist.')

    if draft == DRAFT_MAIN:
      return concept

    # Map the text of examples in main so we can remove them if they are duplicates.
    main_text_ids: dict[Optional[str], str] = {
      example.text: id for id, example in concept.data.items() if example.draft == DRAFT_MAIN
    }

    draft_examples: dict[str, Example] = {
      id: example for id, example in concept.data.items() if example.draft == draft
    }
    for example in draft_examples.values():
      example.draft = DRAFT_MAIN
      # Remove duplicates in main.
      main_text_id = main_text_ids.get(example.text)
      if main_text_id:
        del concept.data[main_text_id]

    concept.version += 1

    self._save(concept)

    return concept


# A singleton concept database.
DISK_CONCEPT_DB = DiskConceptDB()
DISK_CONCEPT_MODEL_DB = DiskConceptModelDB(DISK_CONCEPT_DB)
