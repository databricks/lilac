"""Signals enrich a document with additional metadata."""

from ..signal import (
  Signal,
  SignalInputType,
  TextEmbeddingSignal,
  TextSignal,
  register_embedding,
  register_signal,
)
from .concept_scorer import ConceptSignal
from .default_signals import register_default_signals
from .lang_detection import LangDetectionSignal
from .near_dup import NearDuplicateSignal
from .ner import SpacyNER
from .pii import PIISignal
from .semantic_similarity import SemanticSimilaritySignal
from .text_statistics import TextStatisticsSignal

register_default_signals()

__all__ = [
  'Signal',
  'TextEmbeddingSignal',
  'TextStatisticsSignal',
  'SemanticSimilaritySignal',
  'TextSignal',
  'register_signal',
  'register_embedding',
  'SignalInputType',
  'LangDetectionSignal',
  'NearDuplicateSignal',
  'SpacyNER',
  'PIISignal',
  'ConceptSignal',
]
