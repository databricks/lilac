"""Signal registry."""
from typing import Type, Union

from .signal import Signal

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
