"""Embedding registry."""
from typing import ClassVar, Iterable, Type, Union

import numpy as np
from pydantic import BaseModel, validator

from ..schema import EnrichmentType, RichData

DEFAULT_BATCH_SIZE = 96


class Embedding(BaseModel):
  """A function that embeds text or images."""
  # ClassVars do not get serialized with pydantic.
  name: ClassVar[str]
  enrichment_type: ClassVar[EnrichmentType]
  # We batch this for users so we can write incremental indices and show progress bars.
  batch_size: ClassVar[int] = DEFAULT_BATCH_SIZE

  # The embedding_name will get populated in init automatically from the class name so it gets
  # serialized and the embedding author doesn't have to define both the static property and the
  # field.
  embedding_name: str = 'embedding_base'

  class Config:
    underscore_attrs_are_private = True

  @validator('embedding_name', always=True)
  def validate_embedding_name(cls, embedding_name: str) -> str:
    """Return the static name when the embedding name hasn't yet been set."""
    # When it's already been set from JSON, just return it.
    if embedding_name != 'embedding_base':
      return embedding_name

    if 'name' not in cls.__dict__:
      raise ValueError('Embedding attribute "name" must be defined.')

    return cls.name

  def __call__(self, data: Iterable[RichData]) -> np.ndarray:
    """Call the embedding function."""
    raise NotImplementedError


EmbeddingId = Union[str, Embedding]

EMBEDDING_REGISTRY: dict[str, Type[Embedding]] = {}


def register_embedding(embedding_cls: Type[Embedding]) -> None:
  """Register an embedding in the global registry."""
  if embedding_cls.name in EMBEDDING_REGISTRY:
    raise ValueError(f'Embedding "{embedding_cls.name}" has already been registered!')

  EMBEDDING_REGISTRY[embedding_cls.name] = embedding_cls


def get_embedding_cls(embedding_name: str) -> Type[Embedding]:
  """Return a registered embedding given the name in the registry."""
  if embedding_name not in EMBEDDING_REGISTRY:
    raise ValueError(f'Embedding "{embedding_name}" not found in the registry')

  return EMBEDDING_REGISTRY[embedding_name]


def resolve_embedding(embedding: Union[dict, Embedding]) -> Embedding:
  """Resolve a generic embedding base class to a specific embedding class."""
  if isinstance(embedding, Embedding):
    # The embedding config is already parsed.
    return embedding

  embedding_name = embedding.get('embedding_name')
  if not embedding_name:
    raise ValueError('"embedding_name" needs to be defined in the json dict.')

  return get_embedding_cls(embedding_name)(**embedding)


def clear_embedding_registry() -> None:
  """Clear the embedding registry."""
  EMBEDDING_REGISTRY.clear()
