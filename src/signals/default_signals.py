"""Registers all available default signals."""
from ..embeddings.cohere import Cohere
from ..embeddings.openai import OpenAI
from ..embeddings.palm import PaLM
from ..embeddings.sbert import SBERT
from .concept_scorer import ConceptScoreSignal
from .ner import SpacyNER
from .pii import PIISignal
from .signal import register_signal
from .text_statistics import TextStatisticsSignal


def register_default_signals() -> None:
  """Register all the default signals."""
  # Concepts.
  register_signal(ConceptScoreSignal)

  # Text.
  register_signal(PIISignal)
  register_signal(TextStatisticsSignal)
  register_signal(SpacyNER)

  # Embeddings.
  register_signal(Cohere)
  register_signal(SBERT)
  register_signal(OpenAI)
  register_signal(PaLM)
