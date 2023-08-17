"""Signals enrich a document with additional metadata."""

from ..signal import Signal, SignalInputType, TextEmbeddingSignal, TextSignal, register_signal
from .concept_scorer import ConceptSignal
from .lang_detection import LangDetectionSignal
from .near_dup import NearDuplicateSignal
from .ner import SpacyNER
from .pii import PIISignal

__all__ = [
  'Signal',
  'TextEmbeddingSignal',
  'TextSignal',
  'register_signal',
  'SignalInputType',
  'LangDetectionSignal',
  'NearDuplicateSignal',
  'SpacyNER',
  'PIISignal',
  'ConceptSignal',
]
