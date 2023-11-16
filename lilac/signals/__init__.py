"""Signals enrich a document with additional metadata."""

from ..signal import Signal, SignalInputType, TextEmbeddingSignal, TextSignal, register_signal
from .cluster_hdbscan import ClusterHDBScan
from .concept_scorer import ConceptSignal
from .default_signals import register_default_signals
from .lang_detection import LangDetectionSignal
from .near_dup import NearDuplicateSignal
from .ner import SpacyNER
from .pii import PIISignal
from .text_statistics import TextStatisticsSignal

register_default_signals()

__all__ = [
  'Signal',
  'TextEmbeddingSignal',
  'TextStatisticsSignal',
  'TextSignal',
  'register_signal',
  'SignalInputType',
  'LangDetectionSignal',
  'NearDuplicateSignal',
  'SpacyNER',
  'PIISignal',
  'ConceptSignal',
  'ClusterHDBScan',
]
