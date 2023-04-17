"""Registers all available default signals."""
from .pii import PIISignal
from .signal_registry import register_signal
from .splitters.text_splitter_spacy import SentenceSplitterSpacy
from .text_statistics import TextStatisticsSignal


def register_default_signals() -> None:
  """Register all the default signals."""
  # Text.
  register_signal(PIISignal)
  register_signal(SentenceSplitterSpacy)
  register_signal(TextStatisticsSignal)
