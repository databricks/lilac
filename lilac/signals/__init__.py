"""Signals enrich a document with additional metadata."""

from .lang_detection import LangDetectionSignal
from .near_dup import NearDuplicateSignal
from .ner import SpacyNER
from .pii import PIISignal
from .signal import Signal

__all__ = [
  'Signal',
  'LangDetectionSignal',
  'NearDuplicateSignal',
  'SpacyNER',
  'PIISignal',
]
