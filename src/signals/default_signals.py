"""Registers all available default signals."""
from ..embeddings.cohere import Cohere
from ..embeddings.sbert import SBERT
from .concept_scorer import ConceptScoreSignal
from .pii import PIISignal
from .semantic_search import SemanticSearchSignal
from .signal import register_signal
from .splitters.text_splitter_spacy import SentenceSplitterSpacy
from .substring_search import SubstringSignal
from .text_statistics import TextStatisticsSignal


def register_default_signals() -> None:
  """Register all the default signals."""
  # Concepts.
  register_signal(ConceptScoreSignal)

  # Text.
  register_signal(PIISignal)
  register_signal(SentenceSplitterSpacy)
  register_signal(TextStatisticsSignal)
  register_signal(SubstringSignal)

  # Embeddings.
  register_signal(Cohere)
  register_signal(SBERT)

  # Text embedding inputs.
  register_signal(SemanticSearchSignal)
