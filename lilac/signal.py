"""Interface for implementing a signal."""

import abc
import copy
from typing import (
  Any,
  Callable,
  ClassVar,
  Iterable,
  Optional,
  Sequence,
  Type,
  TypeVar,
  Union,
)

from pydantic import BaseModel, ConfigDict, model_serializer
from pydantic import Field as PydanticField
from typing_extensions import override

from .embeddings.vector_store import VectorDBIndex
from .schema import (
  EMBEDDING_KEY,
  EmbeddingInputType,
  Field,
  Item,
  PathKey,
  RichData,
  SignalInputType,
  field,
)


def _signal_schema_extra(schema: dict[str, Any], signal: Type['Signal']) -> None:
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


class Signal(BaseModel):
  """Interface for signals to implement. A signal can score documents and a dataset column."""

  # ClassVars do not get serialized with pydantic.
  name: ClassVar[str]
  # The display name is just used for rendering in the UI.
  display_name: ClassVar[Optional[str]]

  # The input type is used to populate the UI to determine what the signal accepts as input.
  input_type: ClassVar[SignalInputType]

  @model_serializer(mode='wrap', when_used='always')
  def serialize_model(self, serializer: Callable[..., dict[str, Any]]) -> dict[str, Any]:
    """Serialize the model to a dictionary."""
    res = serializer(self)
    res['signal_name'] = self.name
    return res

  model_config = ConfigDict(extra='ignore', json_schema_extra=_signal_schema_extra)

  def fields(self) -> Field:
    """Return the fields schema for this signal.

    Returns:
      A Field object that describes the schema of the signal.
    """
    raise NotImplementedError

  def compute(self, data: Iterable[RichData]) -> Iterable[Optional[Item]]:
    """Compute the signal for an iterable of documents or images.

    Args:
      data: An iterable of rich data to compute the signal over.
      user: User information, if the user is logged in. This is useful if signals are access
        controlled, like concepts.

    Returns:
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
    args_dict = self.model_dump(exclude_unset=True, exclude_defaults=True)
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
    return f' {self.__class__.__name__}({self.model_dump_json(exclude_none=True)})'


def _args_key_from_dict(args_dict: dict[str, Any]) -> str:
  args = None
  args_list: list[str] = []
  for k, v in args_dict.items():
    if v:
      args_list.append(f'{k}={v}')

  args = ','.join(args_list)
  return '' if not args_list else f'({args})'


# Signal base classes, used for inferring the dependency chain required for computing a signal.
class TextSignal(Signal):
  """An interface for signals that compute over text."""

  input_type: ClassVar[SignalInputType] = SignalInputType.TEXT

  @override
  def key(self, is_computed_signal: Optional[bool] = False) -> str:
    args_dict = self.model_dump(exclude_unset=True, exclude_defaults=True)
    if 'signal_name' in args_dict:
      del args_dict['signal_name']
    return self.name + _args_key_from_dict(args_dict)


class TextEmbeddingSignal(TextSignal):
  """An interface for signals that compute embeddings for text."""

  input_type: ClassVar[SignalInputType] = SignalInputType.TEXT
  embed_input_type: EmbeddingInputType = PydanticField(
    title='Embedding Input Type', default='document', description='The input type to the embedding.'
  )

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


def _vector_signal_schema_extra(schema: dict[str, Any], signal: Type['Signal']) -> None:
  """Add the enum values for embeddings."""
  embeddings: list[str] = []
  for s in SIGNAL_REGISTRY.values():
    if issubclass(s, TextEmbeddingSignal):
      embeddings.append(s.name)

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

  schema['properties']['embedding']['enum'] = embeddings


class VectorSignal(Signal, abc.ABC):
  """An interface for signals that can compute items given vector inputs."""

  embedding: str = PydanticField(description='The name of the pre-computed embedding.')

  model_config = ConfigDict(json_schema_extra=_vector_signal_schema_extra)

  @abc.abstractmethod
  def vector_compute(
    self, keys: Iterable[PathKey], vector_index: VectorDBIndex
  ) -> Iterable[Optional[Item]]:
    """Compute the signal for an iterable of keys that point to documents or images.

    Args:
      keys: An iterable of value ids (at row-level or lower) to lookup precomputed embeddings.
      vector_index: The vector index to lookup pre-computed embeddings.

    Returns:
      An iterable of items. Sparse signals should return "None" for skipped inputs.
    """
    raise NotImplementedError

  def vector_compute_topk(
    self, topk: int, vector_index: VectorDBIndex, rowids: Optional[Iterable[str]] = None
  ) -> Sequence[tuple[PathKey, Optional[Item]]]:
    """Return signal results only for the top k documents or images.

    Signals decide how to rank each document/image in the dataset, usually by a similarity score
    obtained via the vector store.

    Args:
      topk: The number of items to return, ranked by the signal.
      vector_index: The vector index to lookup pre-computed embeddings.
      rowids: Optional iterable of row ids to restrict the search to.

    Returns:
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
    raise ValueError(
      f'"{signal_name}" is a `{signal_cls.__name__}`, '
      f'which is not a subclass of `{signal_type.__name__}`.'
    )
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

  signal_name = signal.get('signal_name')
  if not signal_name:
    raise ValueError('"signal_name" needs to be defined in the json dict.')

  signal_cls = get_signal_cls(signal_name)
  if not signal_cls:
    # Make a metaclass so we get a valid `Signal` class.
    signal_cls = type(f'Signal_{signal_name}', (Signal,), {'name': signal_name})

  signal = copy.deepcopy(signal)
  del signal['signal_name']
  return signal_cls(**signal)


def clear_signal_registry() -> None:
  """Clear the signal registry."""
  SIGNAL_REGISTRY.clear()
