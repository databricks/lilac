"""Interface for implementing a signal."""

import abc
from typing import Any, ClassVar, Iterable, Optional, Sequence, Type, TypeVar, Union

from pydantic import BaseModel, Extra, validator
from typing_extensions import override

from ..embeddings.vector_store import VectorStore
from ..schema import Field, Item, RichData, SignalInputType, VectorKey, field

EMBEDDING_KEY = 'embedding'


class Signal(abc.ABC, BaseModel):
  """Interface for signals to implement. A signal can score documents and a dataset column."""
  # ClassVars do not get serialized with pydantic.
  name: ClassVar[str]
  # The display name is just used for rendering in the UI.
  display_name: ClassVar[Optional[str]]

  signal_type: ClassVar[Type['Signal']]
  # The input type is used to populate the UI for signals that require other signals. For example,
  # if a signal is an TextEmbeddingModelSignal, it computes over embeddings, but it's input type
  # will be text.
  input_type: ClassVar[SignalInputType]
  # The compute type defines what should be passed to compute().
  compute_type: ClassVar[SignalInputType]

  # The signal_name will get populated in init automatically from the class name so it gets
  # serialized and the signal author doesn't have to define both the static property and the field.
  signal_name: Optional[str] = None

  class Config:
    underscore_attrs_are_private = True
    extra = Extra.forbid

    @staticmethod
    def schema_extra(schema: dict[str, Any], signal: Type['Signal']) -> None:
      """Add the title to the schema from the display name and name.

      Pydantic defaults this to the class name.
      """
      if hasattr(signal, 'display_name'):
        schema['title'] = signal.display_name
      if hasattr(signal, 'name'):
        schema['properties']['signal_name']['enum'] = [signal.name]

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

  def compute(self, data: Iterable[RichData]) -> Iterable[Optional[Item]]:
    """Compute the signal for an iterable of documents or images.

    Args:
      data: An iterable of rich data to compute the signal over.
      user: User information, if the user is logged in. This is useful if signals are access
        controlled, like concepts.

    Returns
      An iterable of items. Sparse signals should return "None" for skipped inputs.
    """
    raise NotImplementedError

  def vector_compute(self, keys: Iterable[VectorKey],
                     vector_store: VectorStore) -> Iterable[Optional[Item]]:
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
      keys: Optional[Iterable[VectorKey]] = None) -> Sequence[tuple[VectorKey, Optional[Item]]]:
    """Return signal results only for the top k documents or images.

    Signals decide how to rank each document/image in the dataset, usually by a similarity score
    obtained via the vector store.

    Args:
      topk: The number of items to return, ranked by the signal.
      vector_store: The vector store to lookup pre-computed embeddings.
      keys: Optional iterable of row ids to restrict the search to.

    Returns
      A list of (key, signal_output) tuples containing the `topk` items. Sparse signals should
      return "None" for skipped inputs.
    """
    raise NotImplementedError

  def key(self, is_computed_signal: Optional[bool] = False) -> str:
    """Get the key for a signal.

    This is used to make sure signals with multiple arguments do not collide.

    NOTE: Overriding this method is sensitive. If you override it, make sure that it is globally
    unique. It will be used as the dictionary key for enriched values.

    Args:
      is_computed_signal: True when the signal is computed over the column and written to
        disk. False when the signal is used as a preview UDF.
    """
    args_dict = self.dict(exclude_unset=True, exclude_defaults=True)
    # If a user explicitly defines a signal name for whatever reason, remove it as it's redundant.
    if 'signal_name' in args_dict:
      del args_dict['signal_name']

    return self.name + _args_key_from_dict(args_dict)

  def setup(self) -> None:
    """Setup the signal."""
    pass

  def teardown(self) -> None:
    """Tears down the signal."""
    pass


def _args_key_from_dict(args_dict: dict[str, Any]) -> str:
  args = None
  args_list: list[str] = []
  for k, v in args_dict.items():
    if v:
      args_list.append(f'{k}={v}')

  args = ','.join(args_list)
  return '' if not args_list else f'({args})'


class TextSplitterSignal(Signal):
  """An interface for signals that compute over text."""
  input_type = SignalInputType.TEXT
  compute_type = SignalInputType.TEXT

  @override
  def fields(self) -> Field:
    return field(fields=['string_span'])


# Signal base classes, used for inferring the dependency chain required for computing a signal.
class TextSignal(Signal):
  """An interface for signals that compute over text."""
  input_type = SignalInputType.TEXT
  compute_type = SignalInputType.TEXT

  @override
  def key(self, is_computed_signal: Optional[bool] = False) -> str:
    args_dict = self.dict(exclude_unset=True, exclude_defaults=True)
    if 'signal_name' in args_dict:
      del args_dict['signal_name']
    return self.name + _args_key_from_dict(args_dict)


class TextEmbeddingSignal(TextSignal):
  """An interface for signals that compute embeddings for text."""
  input_type = SignalInputType.TEXT
  compute_type = SignalInputType.TEXT

  _split = True

  def __init__(self, split: bool = True, **kwargs: Any):
    super().__init__(**kwargs)
    self._split = split

  @override
  def fields(self) -> Field:
    """NOTE: Override this method at your own risk if you want to add extra metadata.

    Embeddings should not come with extra metadata.
    """
    return field(fields=[field('string_span', fields={EMBEDDING_KEY: 'embedding'})])


class TextEmbeddingModelSignal(TextSignal):
  """An interface for signals that take embeddings and produce items."""
  input_type = SignalInputType.TEXT
  # compute() takes embeddings, while it operates over text fields by transitively computing splits
  # and embeddings.
  compute_type = SignalInputType.TEXT_EMBEDDING

  embedding: str
  _embedding_signal: Optional[TextEmbeddingSignal] = None

  def __init__(self, **kwargs: Any):
    super().__init__(**kwargs)

    # Validate the embedding signal is registered and the correct type.
    # TODO(nsthorat): Allow arguments passed to the embedding signal.
    self._embedding_signal = get_signal_by_type(self.embedding, TextEmbeddingSignal)()

  def get_embedding_signal(self) -> TextEmbeddingSignal:
    """Return the embedding signal."""
    assert self._embedding_signal is not None
    return self._embedding_signal

  @override
  def key(self, is_computed_signal: Optional[bool] = False) -> str:
    # NOTE: The embedding and split already exists in the path structure. This means we do not
    # need to provide the signal names as part of the key, which still guarantees uniqueness.

    args_dict = self.dict(exclude_unset=True)
    if 'signal_name' in args_dict:
      del args_dict['signal_name']
    del args_dict['embedding']
    return self.name + _args_key_from_dict(args_dict)


Tsignal = TypeVar('Tsignal', bound=Signal)


def get_signal_by_type(signal_name: str, signal_type: Type[Tsignal]) -> Type[Tsignal]:
  """Return a signal class by name and signal type."""
  if signal_name not in SIGNAL_REGISTRY:
    raise ValueError(f'Signal "{signal_name}" not found in the registry')

  signal_cls = SIGNAL_REGISTRY[signal_name]
  if not issubclass(signal_cls, signal_type):
    raise ValueError(f'"{signal_name}" is a `{signal_cls.__name__}`, '
                     f'which is not a subclass of `{signal_type.__name__}`.')
  return signal_cls


def get_signals_by_type(signal_type: Type[Tsignal]) -> list[Type[Tsignal]]:
  """Return all signals that match a signal type."""
  signal_clses: list[Type[Tsignal]] = []
  for signal_cls in SIGNAL_REGISTRY.values():
    if issubclass(signal_cls, signal_type):
      signal_clses.append(signal_cls)
  return signal_clses


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
