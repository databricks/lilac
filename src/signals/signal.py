"""Interface for implementing a signal."""

import abc
from typing import Any, ClassVar, Iterable, Optional, Type, Union, cast

from pydantic import BaseModel
from pydantic import Field as PydanticField
from pydantic import validator
from typing_extensions import override

from ..embeddings.vector_store import VectorStore
from ..schema import Field, PathTuple, RichData, SignalInputType, SignalOut, field

SIGNAL_TYPE_PYDANTIC_FIELD = 'signal_type'


class Signal(abc.ABC, BaseModel):
  """Interface for signals to implement. A signal can score documents and a dataset column."""
  # ClassVars do not get serialized with pydantic.
  name: ClassVar[str]
  signal_type: ClassVar[Type['Signal']]
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

    return self.name + _args_key_from_dict(args_dict)


def _args_key_from_dict(args_dict: dict[str, Any]) -> str:
  args = None
  args_list: list[str] = []
  for k, v in args_dict.items():
    if v:
      args_list.append(f'{k}={v}')

  args = ','.join(args_list)
  return '' if not args_list else f'({args})'


SIGNAL_TYPE_TEXT_EMBEDDING = 'text_embedding'
SIGNAL_TYPE_TEXT_SPLITTER = 'text_splitter'


class TextSplitterSignal(Signal):
  """An interface for signals that compute over text."""
  input_type = SignalInputType.TEXT

  @override
  def fields(self) -> Field:
    return field(['string_span'])


# Signal base classes, used for inferring the dependency chain required for computing a signal.
class TextSignal(Signal):
  """An interface for signals that compute over text."""
  input_type = SignalInputType.TEXT
  split: Optional[str] = PydanticField(
    extra={SIGNAL_TYPE_PYDANTIC_FIELD: SIGNAL_TYPE_TEXT_SPLITTER})
  _split_signal: Optional[TextSplitterSignal] = None

  def __init__(self, split: Optional[str] = None, **kwargs: Any):
    super().__init__(split=split, **kwargs)

    # Validate the split signal is registered and the correct type.
    # TODO(nsthorat): Allow arguments passed to the embedding signal.
    if self.split:
      self._split_signal = cast(
        TextSplitterSignal,
        get_signal_by_type(self.split, SIGNAL_TYPE_TEXT_SPLITTER)(split=self.split))

  def get_split_signal(self) -> Optional[TextSplitterSignal]:
    """Return the embedding signal."""
    return self._split_signal

  @override
  def key(self) -> str:
    # NOTE: The split already exists in the path structure. This means we do not need to provide
    # the signal names as part of the key, which still guarantees uniqueness.

    args_dict = self.dict(exclude_unset=True)
    if 'signal_name' in args_dict:
      del args_dict['signal_name']
    if 'split' in args_dict:
      del args_dict['split']

    return self.name + _args_key_from_dict(args_dict)


class TextEmbeddingSignal(TextSignal):
  """An interface for signals that compute embeddings for text."""
  input_type = SignalInputType.TEXT

  def fields(self) -> Field:
    """Return the fields for the embedding."""
    return field('embedding')


class TextEmbeddingModelSignal(TextSignal):
  """An interface for signals that take embeddings and produce items."""
  input_type = SignalInputType.TEXT_EMBEDDING

  embedding: str = PydanticField(extra={SIGNAL_TYPE_PYDANTIC_FIELD: SIGNAL_TYPE_TEXT_EMBEDDING})
  _embedding_signal: TextEmbeddingSignal

  def __init__(self, embedding: str, **kwargs: Any):
    super().__init__(embedding=embedding, **kwargs)

    # Validate the embedding signal is registered and the correct type.
    # TODO(nsthorat): Allow arguments passed to the embedding signal.
    self._embedding_signal = cast(
      TextEmbeddingSignal,
      get_signal_by_type(self.embedding, SIGNAL_TYPE_TEXT_EMBEDDING)(split=self.split))

  def get_embedding_signal(self) -> Optional[TextEmbeddingSignal]:
    """Return the embedding signal."""
    return self._embedding_signal

  @override
  def key(self) -> str:
    # NOTE: The embedding and split already exists in the path structure. This means we do not
    # need to provide the signal names as part of the key, which still guarantees uniqueness.

    args_dict = self.dict(exclude_unset=True)
    if 'signal_name' in args_dict:
      del args_dict['signal_name']
    del args_dict['embedding']
    if 'split' in args_dict:
      del args_dict['split']

    return self.name + _args_key_from_dict(args_dict)


SIGNAL_TYPE_CLS: dict[str, Type[Signal]] = {
  SIGNAL_TYPE_TEXT_EMBEDDING: TextEmbeddingSignal,
  SIGNAL_TYPE_TEXT_SPLITTER: TextSplitterSignal
}


def get_signal_by_type(signal_name: str, signal_type: str) -> Type[Signal]:
  """Return a signal class by name and signal type."""
  if signal_name not in SIGNAL_REGISTRY:
    raise ValueError(f'Signal "{signal_name}" not found in the registry')

  if signal_type not in SIGNAL_TYPE_CLS:
    raise ValueError(
      f'Invalid `signal_type` "{signal_type}". Valid signal types: {SIGNAL_TYPE_CLS.keys()}')

  signal_subclass = SIGNAL_TYPE_CLS[signal_type]
  signal_cls = SIGNAL_REGISTRY[signal_name]
  if not issubclass(signal_cls, signal_subclass):
    raise ValueError(
      f'"{signal_name}" is a `{signal_cls.__name__}`, '
      f'which is not a `signal_type` "{signal_type}", a subclass of `{signal_subclass.__name__}`.')
  return signal_cls


def get_signal_type(signal_cls: Type[Signal]) -> Optional[str]:
  """Return the signal type for a signal class."""
  for signal_type, signal_subclass in SIGNAL_TYPE_CLS.items():
    if issubclass(signal_cls, signal_subclass):
      return signal_type
  return None


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
