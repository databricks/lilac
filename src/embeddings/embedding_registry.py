"""Embedding registry."""
from typing import ClassVar, Type, Union

from ..signals.signal import Signal

DEFAULT_BATCH_SIZE = 96


class Embedding(Signal):
  """A function that embeds text or images."""
  # We batch this for users so we can write incremental indices and show progress bars.
  batch_size: ClassVar[int] = DEFAULT_BATCH_SIZE


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
