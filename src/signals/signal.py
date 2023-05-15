"""Interface for implementing a signal."""

import abc
from typing import ClassVar, Iterable, Optional, Type, TypeVar, Union

from pydantic import BaseModel
from pydantic import Field as PydanticField
from pydantic import validator
from typing_extensions import override

from ..embeddings.vector_store import VectorStore
from ..schema import DataType, Field, PathTuple, RichData, SignalInputType, SignalOut

SIGNAL_TYPE_PYDANTIC_FIELD = '__signal_type__'


class Signal(abc.ABC, BaseModel):
  """Interface for signals to implement. A signal can score documents and a dataset column."""
  # ClassVars do not get serialized with pydantic.
  name: ClassVar[str]
  input_type: ClassVar[SignalInputType]

  # The signal_name will get populated in init automatically from the class name so it gets
  # serialized and the signal author doesn't have to define both the static property and the field.
  signal_name: Optional[str]

  class Config:
    underscore_attrs_are_private = True

  @validator('signal_name', pre=True, always=True)
  def validate_signal_name(cls, signal_name: str) -> str:
    """Return the static name when the signal name hasn't yet been set."""
    # When it's already been set from JSON, just return it.
    if signal_name:
      return signal_name

    if 'name' not in cls.__dict__:
      raise ValueError('Signal attribute "name" must be defined.')

    return cls.name

  @abc.abstractmethod
  def fields(self) -> Field:
    """Return the fields schema for this signal.

    Returns
      A Field object that describes the schema of the signal.
    """
    pass

  def compute(self, data: Iterable[RichData]) -> Iterable[Optional[SignalOut]]:
    """Compute the signal for an iterable of documents or images.

    Args:
      data: An iterable of rich data to compute the signal over.

    Returns
      An iterable of items. Sparse signals should return "None" for skipped inputs.
    """
    raise NotImplementedError

  def vector_compute(self, keys: Iterable[PathTuple],
                     vector_store: VectorStore) -> Iterable[Optional[SignalOut]]:
    """Compute the signal for an iterable of keys that point to documents or images.

    Args:
      keys: An iterable of value ids (at row-level or lower) to lookup precomputed embeddings.
      vector_store: The vector store to lookup pre-computed embeddings.

    Returns
      An iterable of items. Sparse signals should return "None" for skipped inputs.
    """
    raise NotImplementedError

  def vector_compute_topk(
      self,
      topk: int,
      vector_store: VectorStore,
      keys: Optional[Iterable[PathTuple]] = None) -> list[tuple[PathTuple, Optional[SignalOut]]]:
    """Return signal results only for the top k documents or images.

    Signals decide how to rank each document/image in the dataset, usually by a similarity score
    obtained via the vector store.

    Args:
      topk: The number of items to return, ranked by the signal.
      vector_store: The vector store to lookup pre-computed embeddings.
      keys: Optional iterable of row ids to restrict the search to.

    Returns
      A list of (key, signal_output) tuples containing the "topk" items. Sparse signals should
      return "None" for skipped inputs.
    """
    raise NotImplementedError

  def key(self) -> str:
    """Get the key for a signal.

    This is used to make sure signals with multiple arguments do not collide.

    NOTE: Overriding this method is sensitive. If you override it, make sure that it is globally
    unique. It will be used as the dictionary key for enriched values.
    """
    args_dict = self.dict(exclude_unset=True)
    # If a user explicitly defines a signal name for whatever reason, remove it as it's redundant.
    if 'signal_name' in args_dict:
      del args_dict['signal_name']
    args = None
    args_list: list[str] = []
    for k, v in args_dict.items():
      if v:
        args_list.append(f'{k}={v}')

    args = ','.join(args_list)
    display_args = '' if not args_list else f'({args})'
    return self.name + display_args


SIGNAL_TYPE_TEXT_EMBEDDING = 'text_embedding'
SIGNAL_TYPE_TEXT_SPLITTER = 'text_splitter'


# Signal base classes, used for inferring the dependency chain required for computing a signal.
class TextSignal(Signal):
  """An interface for signals that compute over text."""
  input_type = SignalInputType.TEXT
  # TODO(nsthorat): split should be a union of literals.
  split: Optional[str]

  @validator('split', pre=True)
  def parse_split(cls, split: str) -> str:
    """Parse a signal to its specific subclass instance."""
    # Validate the split signal is registered.
    return get_text_splitter_cls(split).name


class TextSplitterSignal(Signal):
  """An interface for signals that compute over text."""
  input_type = SignalInputType.TEXT

  @override
  def fields(self) -> Field:
    return Field(repeated_field=Field(dtype=DataType.STRING_SPAN))


class TextEmbeddingSignal(TextSignal):
  """An interface for signals that compute embeddings for text."""
  input_type = SignalInputType.TEXT

  def fields(self) -> Field:
    """Return the fields for the embedding."""
    return Field(dtype=DataType.EMBEDDING)


class TextEmbeddingModelSignal(TextSignal):
  """An interface for signals that take embeddings and produce items."""
  input_type = SignalInputType.TEXT_EMBEDDING
  # TODO(nsthorat): Allow this to be an embedding signal if we want to allow python users to pass
  # an embedding signal without registering it.
  embedding: str = PydanticField(extra={SIGNAL_TYPE_PYDANTIC_FIELD: SIGNAL_TYPE_TEXT_EMBEDDING})

  @validator('embedding', pre=True)
  def parse_embedding(cls, embedding: str) -> str:
    """Parse a signal to its specific subclass instance."""
    # Validate the embedding is registered.
    return get_text_embedding_cls(embedding).name


SIGNAL_TYPE_CLS: dict[str, Type[Signal]] = {
  SIGNAL_TYPE_TEXT_EMBEDDING: TextEmbeddingSignal,
  SIGNAL_TYPE_TEXT_SPLITTER: TextSplitterSignal
}

Tsignalcls = TypeVar('Tsignalcls', bound=Signal)


def _signals_by_type(signal_subclass: Type[Tsignalcls]) -> list[Type[Tsignalcls]]:
  """Return all registered signals that are subclasses of the given signal class."""
  return [
    signal_cls for signal_cls in SIGNAL_REGISTRY.values()
    if issubclass(signal_cls, signal_subclass)
  ]


def _one_signal_by_type(signal_name: str, signal_type: str) -> Type[Signal]:
  if signal_name not in SIGNAL_REGISTRY:
    raise ValueError(f'Signal "{signal_name}" not found in the registry')

  signal_cls = SIGNAL_REGISTRY[signal_name]
  if not issubclass(signal_cls, signal_subclass):
    raise ValueError(
      f'`{signal_name}` is a `{signal_cls.__name__}`, not a `{signal_subclass.__name__}`.')
  return signal_cls


def get_text_embedding_clses() -> list[Type[TextEmbeddingSignal]]:
  """Return all registered embedding signals."""
  return _signals_by_type(TextEmbeddingSignal)


def get_text_embedding_cls(signal_name: str) -> Type[TextEmbeddingSignal]:
  """Return a registered text embedding signal given the name in the registry."""
  return _one_signal_by_type(signal_name, TextEmbeddingSignal)


def get_text_splitter_clses() -> list[Type[TextSplitterSignal]]:
  """Return all registered text splitter signals."""
  return _signals_by_type(TextSplitterSignal)


def get_text_splitter_cls(signal_name: str) -> Type[TextSplitterSignal]:
  """Return a registered text splitter signal given the name in the registry."""
  return _one_signal_by_type(signal_name, TextSplitterSignal)


SIGNAL_REGISTRY: dict[str, Type[Signal]] = {}


def register_signal(signal_cls: Type[Signal]) -> None:
  """Register a signal in the global registry."""
  if signal_cls.name in SIGNAL_REGISTRY:
    raise ValueError(f'Signal "{signal_cls.name}" has already been registered!')

  SIGNAL_REGISTRY[signal_cls.name] = signal_cls


def get_signal_cls(signal_name: str) -> Type[Signal]:
  """Return a registered signal given the name in the registry."""
  if signal_name not in SIGNAL_REGISTRY:
    raise ValueError(f'Signal "{signal_name}" not found in the registry')

  return SIGNAL_REGISTRY[signal_name]


def resolve_signal(signal: Union[dict, Signal]) -> Signal:
  """Resolve a generic signal base class to a specific signal class."""
  if isinstance(signal, Signal):
    # The signal config is already parsed.
    return signal

  signal_name = signal.get('signal_name')
  if not signal_name:
    raise ValueError('"signal_name" needs to be defined in the json dict.')

  signal_cls = get_signal_cls(signal_name)
  return signal_cls(**signal)


def clear_signal_registry() -> None:
  """Clear the signal registry."""
  SIGNAL_REGISTRY.clear()
