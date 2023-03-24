"""Splitter registry."""
from typing import Type, Union

from .text_splitter import TextSplitter

SPLITTER_REGISTRY: dict[str, Type[TextSplitter]] = {}


def register_splitter(splitter_cls: Type[TextSplitter]) -> None:
  """Register a splitter in the global registry."""
  if splitter_cls.name in SPLITTER_REGISTRY:
    raise ValueError(f'Splitter "{splitter_cls.name}" has already been registered!')

  SPLITTER_REGISTRY[splitter_cls.name] = splitter_cls


def get_splitter_cls(splitter_name: str) -> Type[TextSplitter]:
  """Return a registered splitter given the name in the registry."""
  if splitter_name not in SPLITTER_REGISTRY:
    raise ValueError(f'Splitter "{splitter_name}" not found in the registry')

  return SPLITTER_REGISTRY[splitter_name]


def resolve_splitter(splitter: Union[dict, TextSplitter]) -> TextSplitter:
  """Resolve a generic splitter base class to a specific splitter class."""
  if isinstance(splitter, TextSplitter):
    # The splitter config is already parsed.
    print('splitta', splitter, type(splitter))
    return splitter

  splitter_name = splitter.get('splitter_name')
  if not splitter_name:
    raise ValueError('"splitter_name" needs to be defined in the json dict.')

  splitter_cls = get_splitter_cls(splitter_name)
  return splitter_cls(**splitter)


def clear_splitter_registry() -> None:
  """Clear the splitter registry."""
  SPLITTER_REGISTRY.clear()
