"""The concept database."""

import abc
import glob
import json
import os
import pathlib
import pickle
import shutil

# NOTE: We have to import the module for uuid so it can be mocked.
import uuid
from pathlib import Path
from typing import Any, List, Optional, Union, cast

from pydantic import BaseModel
from typing_extensions import override

from ..auth import ConceptAuthorizationException, UserInfo
from ..config import data_path, env
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

CONCEPTS_DIR = 'concept'
DATASET_CONCEPTS_DIR = '.concepts'
CONCEPT_JSON_FILENAME = 'concept.json'


class ConceptNamespaceACL(BaseModel):
  """The access control list for a namespace."""
  # Whether the current user can read concepts in the namespace.
  read: bool
  # Whether the current user can add concepts to the namespace.
  write: bool


class ConceptACL(BaseModel):
  """The access control list for an individual concept."""
  # Whether the current user can read the concept.
  read: bool
  # Whether the current user can edit the concept, including adding examples or deleting the
  # concept.
  write: bool


class ConceptInfo(BaseModel):
  """Information about a concept."""
  namespace: str
  name: str
  description: Optional[str] = None
  type: SignalInputType
  drafts: list[DraftId]

  acls: ConceptACL


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
  def list(self, user: Optional[UserInfo] = None) -> list[ConceptInfo]:
    """List all the concepts."""
    pass

  @abc.abstractmethod
  def namespace_acls(self, namespace: str, user: Optional[UserInfo] = None) -> ConceptNamespaceACL:
    """Return the ACL for a namespace."""
    pass

  @abc.abstractmethod
  def concept_acls(self, namespace: str, name: str, user: Optional[UserInfo] = None) -> ConceptACL:
    """Return the ACL for a concept."""
    pass

  @abc.abstractmethod
  def get(self, namespace: str, name: str, user: Optional[UserInfo] = None) -> Optional[Concept]:
    """Return a concept or None if there isn't one."""
    pass

  @abc.abstractmethod
  def create(self,
             namespace: str,
             name: str,
             type: SignalInputType,
             description: Optional[str] = None,
             user: Optional[UserInfo] = None) -> Concept:
    """Create a concept.

    Args:
      namespace: The namespace of the concept.
      name: The name of the concept.
      type: The input type of the concept.
      description: The description of the concept.
      user: The user creating the concept, if authentication is enabled.
    """
    pass

  @abc.abstractmethod
  def edit(self,
           namespace: str,
           name: str,
           change: ConceptUpdate,
           user: Optional[UserInfo] = None) -> Concept:
    """Edit a concept. If the concept doesn't exist, throw an error."""
    pass

  @abc.abstractmethod
  def remove(self, namespace: str, name: str, user: Optional[UserInfo] = None) -> None:
    """Remove a concept."""
    pass

  @abc.abstractmethod
  def merge_draft(self,
                  namespace: str,
                  name: str,
                  draft: DraftId,
                  user: Optional[UserInfo] = None) -> Concept:
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
             column_info: Optional[ConceptColumnInfo] = None,
             user: Optional[UserInfo] = None) -> ConceptModel:
    """Create the concept model."""
    pass

  @abc.abstractmethod
  def get(self,
          namespace: str,
          concept_name: str,
          embedding_name: str,
          column_info: Optional[ConceptColumnInfo] = None,
          user: Optional[UserInfo] = None) -> Optional[ConceptModel]:
    """Get the model associated with the provided concept the embedding.

    Returns None if the model does not exist.
    """
    pass

  @abc.abstractmethod
  def _save(self, model: ConceptModel) -> None:
    """Save the concept model."""
    pass

  def in_sync(self, model: ConceptModel, user: Optional[UserInfo] = None) -> bool:
    """Return True if the model is up to date with the concept."""
    concept = self._concept_db.get(model.namespace, model.concept_name, user=user)
    if not concept:
      raise ValueError(f'Concept "{model.namespace}/{model.concept_name}" does not exist.')
    return concept.version == model.version

  def sync(self, model: ConceptModel, user: Optional[UserInfo] = None) -> bool:
    """Sync the concept model. Returns true if the model was updated."""
    concept = self._concept_db.get(model.namespace, model.concept_name, user=user)
    if not concept:
      raise ValueError(f'Concept "{model.namespace}/{model.concept_name}" does not exist.')
    model_updated = model.sync(concept)
    if model_updated:
      self._save(model)
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
  def get_models(self, namespace: str, concept_name: str) -> list[ConceptModel]:
    """List all the models associated with a concept."""
    pass

  @abc.abstractmethod
  def get_column_infos(self, namespace: str, concept_name: str) -> list[ConceptColumnInfo]:
    """Get the dataset columns where this concept was applied to."""
    pass


class DiskConceptModelDB(ConceptModelDB):
  """Interface for the concept model database."""

  def __init__(self,
               concept_db: ConceptDB,
               base_dir: Optional[Union[str, pathlib.Path]] = None) -> None:
    super().__init__(concept_db)
    self._base_dir = base_dir

  def _get_base_dir(self) -> str:
    return str(self._base_dir) if self._base_dir else data_path()

  @override
  def create(self,
             namespace: str,
             concept_name: str,
             embedding_name: str,
             column_info: Optional[ConceptColumnInfo] = None,
             user: Optional[UserInfo] = None) -> ConceptModel:
    if self.get(namespace, concept_name, embedding_name, column_info, user=user):
      raise ValueError('Concept model already exists.')
    concept = self._concept_db.get(namespace, concept_name, user=user)
    if not concept:
      raise ValueError(f'Concept "{namespace}/{concept_name}" does not exist.')

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
          column_info: Optional[ConceptColumnInfo] = None,
          user: Optional[UserInfo] = None) -> Optional[ConceptModel]:
    # Make sure the concept exists.
    concept = self._concept_db.get(namespace, concept_name, user=user)
    if not concept:
      raise ValueError(f'Concept "{namespace}/{concept_name}" does not exist.')

    # Make sure that the embedding signal exists.
    if not get_signal_cls(embedding_name):
      raise ValueError(f'Embedding signal "{embedding_name}" not found in the registry.')

    concept_model_path = _concept_model_path(self._get_base_dir(), namespace, concept_name,
                                             embedding_name, column_info)
    if not file_exists(concept_model_path):
      return None

    with open_file(concept_model_path, 'rb') as f:
      return pickle.load(f)

  def _save(self, model: ConceptModel) -> None:
    """Save the concept model."""
    concept_model_path = _concept_model_path(self._get_base_dir(), model.namespace,
                                             model.concept_name, model.embedding_name,
                                             model.column_info)
    with open_file(concept_model_path, 'wb') as f:
      pickle.dump(model, f)

  @override
  def remove(self,
             namespace: str,
             concept_name: str,
             embedding_name: str,
             column_info: Optional[ConceptColumnInfo] = None,
             user: Optional[UserInfo] = None) -> None:
    concept_model_path = _concept_model_path(self._get_base_dir(), namespace, concept_name,
                                             embedding_name, column_info)

    if not file_exists(concept_model_path):
      raise ValueError(f'Concept model {namespace}/{concept_name}/{embedding_name} does not exist.')

    delete_file(concept_model_path)

  @override
  def remove_all(self, namespace: str, concept_name: str, user: Optional[UserInfo] = None) -> None:
    datasets_path = os.path.join(self._get_base_dir(), DATASETS_DIR_NAME)
    # Skip if 'datasets' doesn't exist.
    if not os.path.isdir(datasets_path):
      return

    dirs = glob.iglob(
      os.path.join(datasets_path, '**', DATASET_CONCEPTS_DIR, namespace, concept_name),
      recursive=True)
    for dir in dirs:
      shutil.rmtree(dir, ignore_errors=True)

  @override
  def get_models(self,
                 namespace: str,
                 concept_name: str,
                 user: Optional[UserInfo] = None) -> list[ConceptModel]:
    """List all the models associated with a concept."""
    model_files = glob.iglob(
      os.path.join(get_concept_output_dir(self._get_base_dir(), namespace, concept_name), '*.pkl'))
    models: list[ConceptModel] = []
    for model_file in model_files:
      embedding_name = os.path.basename(model_file)[:-len('.pkl')]
      model = self.get(namespace, concept_name, embedding_name, user=user)
      if model:
        models.append(model)
    return models

  @override
  def get_column_infos(self, namespace: str, concept_name: str) -> list[ConceptColumnInfo]:
    datasets_path = os.path.join(self._get_base_dir(), DATASETS_DIR_NAME)
    # Skip if 'datasets' doesn't exist.
    if not os.path.isdir(datasets_path):
      return []

    dirs = glob.iglob(
      os.path.join(datasets_path, '**', DATASET_CONCEPTS_DIR, namespace, concept_name, '*.pkl'),
      recursive=True)
    result: list[ConceptColumnInfo] = []
    for dir in dirs:
      dir = os.path.relpath(dir, datasets_path)
      dataset_namespace, dataset_name, *path, _, _, _, _ = Path(dir).parts
      result.append(
        ConceptColumnInfo(namespace=dataset_namespace, name=dataset_name, path=tuple(path)))
    return result


def get_concept_output_dir(base_dir: str, namespace: str, name: str) -> str:
  """Return the output directory for a given concept."""
  return os.path.join(base_dir, CONCEPTS_DIR, namespace, name)


def _concept_json_path(base_dir: str, namespace: str, name: str) -> str:
  return os.path.join(get_concept_output_dir(base_dir, namespace, name), CONCEPT_JSON_FILENAME)


def _concept_model_path(base_dir: str,
                        namespace: str,
                        concept_name: str,
                        embedding_name: str,
                        column_info: Optional[ConceptColumnInfo] = None) -> str:
  if not column_info:
    return os.path.join(
      get_concept_output_dir(base_dir, namespace, concept_name), f'{embedding_name}.pkl')

  dataset_dir = get_dataset_output_dir(base_dir, column_info.namespace, column_info.name)
  path_tuple = normalize_path(column_info.path)
  path_without_wildcards = (p for p in path_tuple if p != PATH_WILDCARD)
  path_dir = os.path.join(dataset_dir, *path_without_wildcards)
  return os.path.join(path_dir, DATASET_CONCEPTS_DIR, namespace, concept_name,
                      f'{embedding_name}-neg-{column_info.num_negative_examples}.pkl')


class DiskConceptDB(ConceptDB):
  """A concept database."""

  def __init__(self, base_dir: Optional[Union[str, pathlib.Path]] = None) -> None:
    self._base_dir = base_dir

  def _get_base_dir(self) -> str:
    return str(self._base_dir) if self._base_dir else data_path()

  @override
  def namespace_acls(self, namespace: str, user: Optional[UserInfo] = None) -> ConceptNamespaceACL:
    if not env('LILAC_AUTH_ENABLED'):
      return ConceptNamespaceACL(read=True, write=True)

    if namespace == 'lilac':
      return ConceptNamespaceACL(read=True, write=False)
    if user and user.id == namespace:
      return ConceptNamespaceACL(read=True, write=True)

    return ConceptNamespaceACL(read=False, write=False)

  @override
  def concept_acls(self, namespace: str, name: str, user: Optional[UserInfo] = None) -> ConceptACL:
    namespace_acls = self.namespace_acls(namespace, user=user)
    # Concept ACL inherit from the namespace ACL. We currently don't have concept-specific
    #  ACL.
    return ConceptACL(read=namespace_acls.read, write=namespace_acls.write)

  @override
  def list(self, user: Optional[UserInfo] = None) -> list[ConceptInfo]:
    namespaces: Optional[list[str]] = None
    if env('LILAC_AUTH_ENABLED'):
      namespaces = ['lilac']
      if user:
        namespaces += [user.id]

    # Read the concepts and return a ConceptInfo containing the namespace and name.
    concept_infos = []
    for root, _, files in os.walk(self._get_base_dir()):
      for file in files:
        if file == CONCEPT_JSON_FILENAME:
          namespace, name = root.split('/')[-2:]
          if namespaces and namespace not in namespaces:
            # Ignore concepts that are not in the namespace, if provided.
            continue

          concept = cast(Concept, self.get(namespace, name, user=user))
          concept_infos.append(
            ConceptInfo(
              namespace=namespace,
              name=name,
              description=concept.description,
              type=SignalInputType.TEXT,
              drafts=concept.drafts(),
              acls=self.concept_acls(namespace, name, user=user)))

    return concept_infos

  @override
  def get(self, namespace: str, name: str, user: Optional[UserInfo] = None) -> Optional[Concept]:
    # If the user does not have access to the concept, return None.
    acls = self.concept_acls(namespace, name, user=user)
    if not acls.read:
      raise ConceptAuthorizationException(
        f'Concept "{namespace}/{name}" does not exist or user does not have access.')

    concept_json_path = _concept_json_path(self._get_base_dir(), namespace, name)
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
             description: Optional[str] = None,
             user: Optional[UserInfo] = None) -> Concept:
    """Create a concept."""
    # If the user does not have access to the write to the concept namespace, throw.
    acls = self.namespace_acls(namespace, user=user)
    if not acls.write:
      raise ConceptAuthorizationException(
        f'Concept namespace "{namespace}" does not exist or user does not have access.')

    concept_json_path = _concept_json_path(self._get_base_dir(), namespace, name)
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
  def edit(self,
           namespace: str,
           name: str,
           change: ConceptUpdate,
           user: Optional[UserInfo] = None) -> Concept:
    # If the user does not have access to the concept, return None.
    acls = self.concept_acls(namespace, name, user=user)
    if not acls.write:
      raise ConceptAuthorizationException(
        f'Concept "{namespace}/{name}" does not exist or user does not have access.')

    concept_json_path = _concept_json_path(self._get_base_dir(), namespace, name)

    if not file_exists(concept_json_path):
      raise ValueError(f'Concept with namespace "{namespace}" and name "{name}" does not exist. '
                       'Please call create() first.')

    inserted_points = change.insert or []
    updated_points = change.update or []
    removed_points = change.remove or []

    concept = cast(Concept, self.get(namespace, name, user=user))

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
    concept_json_path = _concept_json_path(self._get_base_dir(), concept.namespace,
                                           concept.concept_name)
    with open_file(concept_json_path, 'w') as f:
      f.write(concept.json(exclude_none=True, indent=2, exclude_defaults=True))

  @override
  def remove(self, namespace: str, name: str, user: Optional[UserInfo] = None) -> None:
    # If the user does not have access to the concept, return None.
    acls = self.concept_acls(namespace, name, user=user)
    if not acls.write:
      raise ConceptAuthorizationException(
        f'Concept "{namespace}/{name}" does not exist or user does not have access.')

    concept_dir = get_concept_output_dir(self._get_base_dir(), namespace, name)

    if not file_exists(concept_dir):
      raise ValueError(f'Concept with namespace "{namespace}" and name "{name}" does not exist.')

    shutil.rmtree(concept_dir, ignore_errors=True)

  @override
  def merge_draft(self,
                  namespace: str,
                  name: str,
                  draft: DraftId,
                  user: Optional[UserInfo] = None) -> Concept:
    """Merge a draft concept."""
    # If the user does not have access to the concept, return None.
    acls = self.concept_acls(namespace, name, user=user)
    if not acls.write:
      raise ConceptAuthorizationException(
        f'Concept "{namespace}/{name}" does not exist or user does not have access.')

    concept = self.get(namespace, name, user=user)
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
