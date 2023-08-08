"""Source registry for the dataset sources."""

from typing import Optional, Type, Union

from .source import Source

SOURCE_REGISTRY: dict[str, Type[Source]] = {}


def register_source(source_cls: Type[Source]) -> None:
  """Register a source configuration globally."""
  if source_cls.name in SOURCE_REGISTRY:
    raise ValueError(f'Source "{source_cls.name}" has already been registered!')

  SOURCE_REGISTRY[source_cls.name] = source_cls


def get_source_cls(source_name: str) -> Optional[Type[Source]]:
  """Return a registered source given the name in the registry."""
  return SOURCE_REGISTRY.get(source_name)


def registered_sources() -> dict[str, Type[Source]]:
  """Return all registered sources."""
  return SOURCE_REGISTRY


def resolve_source(source: Union[dict, Source]) -> Source:
  """Resolve a generic source base class to a specific source class."""
  if isinstance(source, Source):
    # The source is already parsed.
    return source

  source_name = source.get('source_name')
  if not source_name:
    raise ValueError('"source_name" needs to be defined in the json dict.')

  source_cls = get_source_cls(source_name)
  if not source_cls:
    # Make a metaclass so we get a valid `Source` class.
    source_cls = type(f'Source_{source_name}', (Source,), {'name': source_name})
  return source_cls(**source)


def clear_source_registry() -> None:
  """Clear the source registry."""
  SOURCE_REGISTRY.clear()
