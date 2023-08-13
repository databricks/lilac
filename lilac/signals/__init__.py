"""Signals enrich a document with additional metadata."""

from ..signal import Signal
from .concept_scorer import ConceptSignal
from .lang_detection import LangDetectionSignal
from .near_dup import NearDuplicateSignal
from .ner import SpacyNER
from .pii import PIISignal

__all__ = [
  'Signal',
  'LangDetectionSignal',
  'NearDuplicateSignal',
  'SpacyNER',
  'PIISignal',
  'ConceptSignal',
]
