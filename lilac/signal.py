"""Interface for implementing a signal."""

import abc
from typing import TYPE_CHECKING, Any, ClassVar, Iterable, Optional, Sequence, Type, TypeVar, Union

from pydantic import BaseModel, Extra

if TYPE_CHECKING:
  from pydantic.typing import AbstractSetIntStr, MappingIntStrAny

from typing_extensions import override

from .embeddings.vector_store import VectorDBIndex
from .schema import EMBEDDING_KEY, Field, Item, PathKey, RichData, SignalInputType, field


class Signal(BaseModel):
  """Interface for signals to implement. A signal can score documents and a dataset column."""
  # ClassVars do not get serialized with pydantic.
  name: ClassVar[str]
  # The display name is just used for rendering in the UI.
  display_name: ClassVar[Optional[str]]

  # The input type is used to populate the UI to determine what the signal accepts as input.
  input_type: ClassVar[SignalInputType]

  def dict(
    self,
    *,
    include: Optional[Union['AbstractSetIntStr', 'MappingIntStrAny']] = None,
    exclude: Optional[Union['AbstractSetIntStr', 'MappingIntStrAny']] = None,
    by_alias: bool = False,
    skip_defaults: Optional[bool] = None,
    exclude_unset: bool = False,
    exclude_defaults: bool = False,
    exclude_none: bool = False,
  ) -> dict[str, Any]:
    """Override the default dict method to add `signal_name`."""
    res = super().dict(
      include=include,
      exclude=exclude,
      by_alias=by_alias,
      skip_defaults=skip_defaults,
      exclude_unset=exclude_unset,
      exclude_defaults=exclude_defaults,
      exclude_none=exclude_none)
    res['signal_name'] = self.name
    return res

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

      signal_prop: dict[str, Any]
      if hasattr(signal, 'name'):
        signal_prop = {'enum': [signal.name]}
      else:
        signal_prop = {'type': 'string'}
      schema['properties'] = {'signal_name': signal_prop, **schema['properties']}
      if 'required' not in schema:
        schema['required'] = []
      schema['required'].append('signal_name')

  def fields(self) -> Field:
    """Return the fields schema for this signal.

    Returns
      A Field object that describes the schema of the signal.
    """
    raise NotImplementedError

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

  def __str__(self) -> str:
    return f' {self.__class__.__name__}({self.json(exclude_none=True)})'


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

  @override
  def fields(self) -> Field:
    return field(fields=['string_span'])


# Signal base classes, used for inferring the dependency chain required for computing a signal.
class TextSignal(Signal):
  """An interface for signals that compute over text."""
  input_type = SignalInputType.TEXT

  @override
  def key(self, is_computed_signal: Optional[bool] = False) -> str:
    args_dict = self.dict(exclude_unset=True, exclude_defaults=True)
    if 'signal_name' in args_dict:
      del args_dict['signal_name']
    return self.name + _args_key_from_dict(args_dict)


class TextEmbeddingSignal(TextSignal):
  """An interface for signals that compute embeddings for text."""
  input_type = SignalInputType.TEXT

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


class VectorSignal(Signal, abc.ABC):
  """An interface for signals that can compute items given vector inputs."""
  embedding: str

  @abc.abstractmethod
  def vector_compute(self, keys: Iterable[PathKey],
                     vector_index: VectorDBIndex) -> Iterable[Optional[Item]]:
    """Compute the signal for an iterable of keys that point to documents or images.

    Args:
      keys: An iterable of value ids (at row-level or lower) to lookup precomputed embeddings.
      vector_index: The vector index to lookup pre-computed embeddings.

    Returns
      An iterable of items. Sparse signals should return "None" for skipped inputs.
    """
    raise NotImplementedError

  def vector_compute_topk(
      self,
      topk: int,
      vector_index: VectorDBIndex,
      keys: Optional[Iterable[PathKey]] = None) -> Sequence[tuple[PathKey, Optional[Item]]]:
    """Return signal results only for the top k documents or images.

    Signals decide how to rank each document/image in the dataset, usually by a similarity score
    obtained via the vector store.

    Args:
      topk: The number of items to return, ranked by the signal.
      vector_index: The vector index to lookup pre-computed embeddings.
      keys: Optional iterable of row ids to restrict the search to.

    Returns
      A list of (key, signal_output) tuples containing the `topk` items. Sparse signals should
      return "None" for skipped inputs.
    """
    raise NotImplementedError


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


def get_signal_cls(signal_name: str) -> Optional[Type[Signal]]:
  """Return a registered signal given the name in the registry."""
  return SIGNAL_REGISTRY.get(signal_name)


def resolve_signal(signal: Union[dict, Signal]) -> Signal:
  """Resolve a generic signal base class to a specific signal class."""
  if isinstance(signal, Signal):
    # The signal config is already parsed.
    return signal

  signal_name = signal.pop('signal_name')
  if not signal_name:
    raise ValueError('"signal_name" needs to be defined in the json dict.')

  signal_cls = get_signal_cls(signal_name)
  if not signal_cls:
    # Make a metaclass so we get a valid `Signal` class.
    signal_cls = type(f'Signal_{signal_name}', (Signal,), {'name': signal_name})
  return signal_cls(**signal)


def clear_signal_registry() -> None:
  """Clear the signal registry."""
  SIGNAL_REGISTRY.clear()
