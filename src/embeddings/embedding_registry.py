"""Embedding registry."""
import abc
from typing import Any, ClassVar, Iterable, Type, Union

import numpy as np
from pydantic import BaseModel

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

  def __init__(self, *args: Any, **kwargs: Any) -> None:
    super().__init__(*args, **kwargs)

    if 'name' not in self.__class__.__dict__:
      raise ValueError('Embedding attribute "name" must be defined.')

    self.embedding_name = self.__class__.name

  @abc.abstractmethod
  def __call__(self, data: Iterable[RichData]) -> np.ndarray:
    """Call the embedding function."""
    pass


EmbeddingId = Union[str, Type[Embedding]]

EMBEDDING_REGISTRY: dict[str, Type[Embedding]] = {}


def register_embedding(embedding_cls: Type[Embedding]) -> None:
  """Register an embedding in the global registry."""
  if embedding_cls.name in EMBEDDING_REGISTRY:
    raise ValueError(f'Embedding "{embedding_cls.name}" has already been registered!')

  EMBEDDING_REGISTRY[embedding_cls.name] = embedding_cls


def get_embedding_cls(embedding: EmbeddingId) -> Type[Embedding]:
  """Return a registered signal given the name in the registry."""
  if isinstance(embedding, str):
    if embedding not in EMBEDDING_REGISTRY:
      raise ValueError(f'Embedding "{embedding}" not found in the registry')

    return EMBEDDING_REGISTRY[embedding]

  # The embedding is already a class.
  return embedding


def resolve_embedding(embedding: Union[dict, Embedding]) -> Embedding:
  """Resolve a generic signal base class to a specific signal class."""
  if isinstance(embedding, Embedding):
    # The signal config is already parsed.
    return embedding

  embedding_name = embedding.get('embedding_name')
  if not embedding_name:
    raise ValueError('"embedding_name" needs to be defined in the json dict.')

  return get_embedding_cls(embedding_name)(**embedding)


def clear_embedding_registry() -> None:
  """Clear the embedding registry."""
  EMBEDDING_REGISTRY.clear()
