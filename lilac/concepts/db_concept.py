"""The concept database."""

import abc
import glob
import json
import os
import pathlib
import pickle
import shutil
import threading

# NOTE: We have to import the module for uuid so it can be mocked.
import uuid
from importlib import resources
from typing import Any, List, Optional, Union, cast

from pydantic import BaseModel
from typing_extensions import override

from ..auth import ConceptAuthorizationException, UserInfo
from ..env import env, get_project_dir
from ..signal import get_signal_cls
from ..utils import delete_file, file_exists, get_lilac_cache_dir, open_file
from .concept import (
  DRAFT_MAIN,
  Concept,
  ConceptMetadata,
  ConceptModel,
  ConceptType,
  DraftId,
  Example,
  ExampleIn,
)

CONCEPTS_DIR = 'concept'
CONCEPT_JSON_FILENAME = 'concept.json'
# Under 'lilac' package.
LILAC_CONCEPTS_DIR = 'concepts'


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
  type: ConceptType
  metadata: ConceptMetadata

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
  def create(
    self,
    namespace: str,
    name: str,
    type: Union[ConceptType, str],
    metadata: Optional[ConceptMetadata] = None,
    user: Optional[UserInfo] = None,
  ) -> Concept:
    """Create a concept.

    Args:
      namespace: The namespace of the concept.
      name: The name of the concept.
      type: The type of the concept.
      metadata: The metadata for the concept, including tags, description, and visibility.
      user: The user creating the concept, if authentication is enabled.
    """
    pass

  @abc.abstractmethod
  def edit(
    self, namespace: str, name: str, change: ConceptUpdate, user: Optional[UserInfo] = None
  ) -> Concept:
    """Edit a concept. If the concept doesn't exist, throw an error."""
    pass

  @abc.abstractmethod
  def update_metadata(
    self, namespace: str, name: str, metadata: ConceptMetadata, user: Optional[UserInfo] = None
  ) -> None:
    """Update the metadata of a concept.

    Args:
      namespace: The namespace of the concept.
      name: The name of the concept.
      metadata: The metadata to update.
      user: The user updating the metadata, if authentication is enabled.
    """
    pass

  @abc.abstractmethod
  def remove(self, namespace: str, name: str, user: Optional[UserInfo] = None) -> None:
    """Remove a concept."""
    pass

  @abc.abstractmethod
  def merge_draft(
    self, namespace: str, name: str, draft: DraftId, user: Optional[UserInfo] = None
  ) -> Concept:
    """Merge a draft concept.."""
    pass


class ConceptModelDB(abc.ABC):
  """Interface for the concept model database."""

  _concept_db: ConceptDB
  _sync_lock = threading.Lock()

  def __init__(self, concept_db: ConceptDB) -> None:
    self._concept_db = concept_db

  @abc.abstractmethod
  def create(
    self, namespace: str, concept_name: str, embedding_name: str, user: Optional[UserInfo] = None
  ) -> ConceptModel:
    """Create the concept model."""
    pass

  @abc.abstractmethod
  def get(
    self, namespace: str, concept_name: str, embedding_name: str, user: Optional[UserInfo] = None
  ) -> Optional[ConceptModel]:
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

  def sync(
    self,
    namespace: str,
    concept_name: str,
    embedding_name: str,
    user: Optional[UserInfo] = None,
    create: bool = False,
  ) -> ConceptModel:
    """Sync the concept model. Returns true if the model was updated."""
    with self._sync_lock:
      model = self.get(namespace, concept_name, embedding_name, user=user)
      if not model:
        if create:
          model = self.create(namespace, concept_name, embedding_name, user=user)
        else:
          raise ValueError(f'Model "{namespace}/{concept_name}/{embedding_name}" does not exist.')

      concept = self._concept_db.get(model.namespace, model.concept_name, user=user)
      if not concept:
        raise ValueError(f'Concept "{model.namespace}/{model.concept_name}" does not exist.')
      model_updated = model.sync(concept)
      if model_updated:
        self._save(model)
      return model

  @abc.abstractmethod
  def remove(self, namespace: str, concept_name: str, embedding_name: str) -> None:
    """Remove the model of a concept."""
    pass

  @abc.abstractmethod
  def get_models(self, namespace: str, concept_name: str) -> list[ConceptModel]:
    """List all the models associated with a concept."""
    pass


class DiskConceptModelDB(ConceptModelDB):
  """Interface for the concept model database."""

  def __init__(
    self, concept_db: ConceptDB, project_dir: Optional[Union[str, pathlib.Path]] = None
  ) -> None:
    super().__init__(concept_db)
    self._project_dir = project_dir

  def _get_project_dir(self) -> str:
    return str(self._project_dir) if self._project_dir else get_project_dir()

  @override
  def create(
    self, namespace: str, concept_name: str, embedding_name: str, user: Optional[UserInfo] = None
  ) -> ConceptModel:
    if self.get(namespace, concept_name, embedding_name, user=user):
      raise ValueError('Concept model already exists.')
    concept = self._concept_db.get(namespace, concept_name, user=user)
    if not concept:
      raise ValueError(f'Concept "{namespace}/{concept_name}" does not exist.')
    model = ConceptModel(
      namespace=namespace, concept_name=concept_name, embedding_name=embedding_name
    )
    self._save(model)
    return model

  @override
  def get(
    self, namespace: str, concept_name: str, embedding_name: str, user: Optional[UserInfo] = None
  ) -> Optional[ConceptModel]:
    # Make sure the concept exists.
    concept = self._concept_db.get(namespace, concept_name, user=user)
    if not concept:
      raise ValueError(f'Concept "{namespace}/{concept_name}" does not exist.')

    # Make sure that the embedding signal exists.
    if not get_signal_cls(embedding_name):
      raise ValueError(f'Embedding signal "{embedding_name}" not found in the registry.')

    concept_model_path = _concept_model_path(
      self._get_project_dir(), namespace, concept_name, embedding_name
    )
    if not file_exists(concept_model_path):
      return None

    with open_file(concept_model_path, 'rb') as f:
      try:
        return pickle.load(f)
      except BaseException:
        # Pickle serialization failed. We fallback to re-creating the model.
        return None

  def _save(self, model: ConceptModel) -> None:
    """Save the concept model."""
    concept_model_path = _concept_model_path(
      self._get_project_dir(), model.namespace, model.concept_name, model.embedding_name
    )
    with open_file(concept_model_path, 'wb') as f:
      pickle.dump(model, f)

  @override
  def remove(
    self, namespace: str, concept_name: str, embedding_name: str, user: Optional[UserInfo] = None
  ) -> None:
    concept_model_path = _concept_model_path(
      self._get_project_dir(), namespace, concept_name, embedding_name
    )

    if not file_exists(concept_model_path):
      raise ValueError(f'Concept model {namespace}/{concept_name}/{embedding_name} does not exist.')

    delete_file(concept_model_path)

  @override
  def get_models(
    self, namespace: str, concept_name: str, user: Optional[UserInfo] = None
  ) -> list[ConceptModel]:
    """List all the models associated with a concept."""
    model_files = glob.iglob(
      os.path.join(_concept_cache_dir(self._get_project_dir(), namespace, concept_name), '*.pkl')
    )
    models: list[ConceptModel] = []
    for model_file in model_files:
      embedding_name = os.path.basename(model_file)[: -len('.pkl')]
      model = self.get(namespace, concept_name, embedding_name, user=user)
      if model:
        models.append(model)
    return models


def get_concept_output_dir(project_dir: str, namespace: str, name: str) -> str:
  """Return the output directory for a given concept."""
  if namespace == 'lilac':
    # Lilac concepts are stored in the resources directory and shipped with the pip package.
    return str(resources.files('lilac').joinpath(os.path.join(LILAC_CONCEPTS_DIR, name)))

  return os.path.join(project_dir, CONCEPTS_DIR, namespace, name)


def _concept_json_path(project_dir: str, namespace: str, name: str) -> str:
  return os.path.join(get_concept_output_dir(project_dir, namespace, name), CONCEPT_JSON_FILENAME)


def _concept_cache_dir(project_dir: str, namespace: str, concept_name: str) -> str:
  return os.path.join(get_lilac_cache_dir(project_dir), CONCEPTS_DIR, namespace, concept_name)


def _concept_model_path(
  project_dir: str, namespace: str, concept_name: str, embedding_name: str
) -> str:
  return os.path.join(
    _concept_cache_dir(project_dir, namespace, concept_name), f'{embedding_name}.pkl'
  )


class DiskConceptDB(ConceptDB):
  """A concept database."""

  def __init__(self, project_dir: Optional[Union[str, pathlib.Path]] = None) -> None:
    self._project_dir = project_dir

  def _get_project_dir(self) -> str:
    return str(self._project_dir) if self._project_dir else get_project_dir()

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
    read = namespace_acls.read
    if env('LILAC_AUTH_ENABLED'):
      concept = self._read_concept(namespace, name)
      if concept and concept.metadata and concept.metadata.is_public:
        read = True

    # Concept ACL inherit from the namespace ACL. We currently don't have concept-specific
    #  ACL.
    return ConceptACL(read=read, write=namespace_acls.write)

  @override
  def list(self, user: Optional[UserInfo] = None) -> list[ConceptInfo]:
    namespaces: Optional[list[str]] = None
    if env('LILAC_AUTH_ENABLED'):
      namespaces = ['lilac']
      if user:
        namespaces += [user.id]

    concept_infos: list[ConceptInfo] = []

    namespace_concept_dirs: list[tuple[Optional[str], str]] = [
      # None = Read the namespace from the directory.
      (None, os.path.join(self._get_project_dir(), CONCEPTS_DIR)),
      # Read lilac concepts from the resources directory.
      ('lilac', str(resources.files('lilac').joinpath(LILAC_CONCEPTS_DIR))),
    ]

    for default_namespace, concept_dir in namespace_concept_dirs:
      # Read the concepts from the data dir and return a ConceptInfo containing the namespace and
      # name.
      for root, _, files in os.walk(concept_dir):
        for file in files:
          if file == CONCEPT_JSON_FILENAME:
            namespace, name = root.split(os.sep)[-2:]
            if default_namespace is not None:
              namespace = default_namespace
            if namespaces and namespace not in namespaces:
              # Ignore concepts that are not in the namespace, if provided.
              continue

            concept = cast(Concept, self.get(namespace, name, user=user))
            concept_infos.append(
              _info_from_concept(concept, self.concept_acls(namespace, name, user=user))
            )

    return concept_infos

  @override
  def get(self, namespace: str, name: str, user: Optional[UserInfo] = None) -> Optional[Concept]:
    # If the user does not have access to the concept, return None.
    acls = self.concept_acls(namespace, name, user=user)
    if not acls.read:
      raise ConceptAuthorizationException(
        f'Concept "{namespace}/{name}" does not exist or user does not have access.'
      )
    return self._read_concept(namespace, name)

  def _read_concept(self, namespace: str, name: str) -> Optional[Concept]:
    concept_json_path = _concept_json_path(self._get_project_dir(), namespace, name)
    if not file_exists(concept_json_path):
      return None

    with open_file(concept_json_path) as f:
      obj: dict[str, Any] = json.load(f)
      if 'namespace' not in obj:
        obj['namespace'] = namespace
      return Concept.model_validate(obj)

  @override
  def create(
    self,
    namespace: str,
    name: str,
    type: Union[ConceptType, str] = ConceptType.TEXT,
    metadata: Optional[ConceptMetadata] = None,
    user: Optional[UserInfo] = None,
  ) -> Concept:
    """Create a concept."""
    # If the user does not have access to the write to the concept namespace, throw.
    acls = self.namespace_acls(namespace, user=user)
    if not acls.write:
      raise ConceptAuthorizationException(
        f'Concept namespace "{namespace}" does not exist or user does not have access.'
      )

    concept_json_path = _concept_json_path(self._get_project_dir(), namespace, name)
    if file_exists(concept_json_path):
      raise ValueError(f'Concept with namespace "{namespace}" and name "{name}" already exists.')

    if isinstance(type, str):
      type = ConceptType(type)
    concept = Concept(namespace=namespace, concept_name=name, type=type, data={}, metadata=metadata)
    self._save(concept)
    return concept

  def _validate_examples(
    self, examples: List[Union[ExampleIn, Example]], type: ConceptType
  ) -> None:
    for example in examples:
      inferred_type = 'text' if example.text else 'unknown'
      if inferred_type != type:
        raise ValueError(f'Example type "{inferred_type}" does not match concept type "{type}".')

  @override
  def update_metadata(
    self, namespace: str, name: str, metadata: ConceptMetadata, user: Optional[UserInfo] = None
  ) -> None:
    concept = self.get(namespace, name, user=user)
    if not concept:
      raise ValueError('Concept with namespace "{namespace}" and name "{name}" does not exist.')

    concept.metadata = metadata

    self._save(concept)

  @override
  def edit(
    self, namespace: str, name: str, change: ConceptUpdate, user: Optional[UserInfo] = None
  ) -> Concept:
    # If the user does not have access to the concept, return None.
    acls = self.concept_acls(namespace, name, user=user)
    if not acls.write:
      raise ConceptAuthorizationException(
        f'Concept "{namespace}/{name}" does not exist or user does not have access.'
      )

    concept_json_path = _concept_json_path(self._get_project_dir(), namespace, name)

    if not file_exists(concept_json_path):
      raise ValueError(
        f'Concept with namespace "{namespace}" and name "{name}" does not exist. '
        'Please call create() first.'
      )

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
      concept.data[id] = Example(id=id, **example.model_dump())

    for example in updated_points:
      if example.id not in concept.data:
        raise ValueError(f'Example with id "{example.id}" does not exist.')

      # Remove the old example and make a new one with a new id to keep it functional.
      concept.data.pop(example.id)
      concept.data[example.id] = example.model_copy()

    concept.version += 1

    self._save(concept)

    return concept

  def _save(self, concept: Concept) -> None:
    concept_json_path = _concept_json_path(
      self._get_project_dir(), concept.namespace, concept.concept_name
    )
    with open_file(concept_json_path, 'w') as f:
      f.write(concept.model_dump_json(exclude_none=True, indent=2, exclude_defaults=True))

  @override
  def remove(self, namespace: str, name: str, user: Optional[UserInfo] = None) -> None:
    # If the user does not have access to the concept, return None.
    acls = self.concept_acls(namespace, name, user=user)
    if not acls.write:
      raise ConceptAuthorizationException(
        f'Concept "{namespace}/{name}" does not exist or user does not have access.'
      )

    concept_dir = get_concept_output_dir(self._get_project_dir(), namespace, name)

    if not file_exists(concept_dir):
      raise ValueError(f'Concept with namespace "{namespace}" and name "{name}" does not exist.')

    shutil.rmtree(concept_dir, ignore_errors=True)

  @override
  def merge_draft(
    self, namespace: str, name: str, draft: DraftId, user: Optional[UserInfo] = None
  ) -> Concept:
    """Merge a draft concept."""
    # If the user does not have access to the concept, return None.
    acls = self.concept_acls(namespace, name, user=user)
    if not acls.write:
      raise ConceptAuthorizationException(
        f'Concept "{namespace}/{name}" does not exist or user does not have access.'
      )

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


def _info_from_concept(concept: Concept, acls: ConceptACL) -> ConceptInfo:
  metadata = concept.metadata or ConceptMetadata()
  return ConceptInfo(
    namespace=concept.namespace,
    name=concept.concept_name,
    metadata=metadata,
    type=concept.type,
    drafts=concept.drafts(),
    acls=acls,
  )


# A singleton concept database.
DISK_CONCEPT_DB = DiskConceptDB()
DISK_CONCEPT_MODEL_DB = DiskConceptModelDB(DISK_CONCEPT_DB)
