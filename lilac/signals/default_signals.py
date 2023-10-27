"""Registers all available default signals."""
from ..embeddings.cohere import Cohere
from ..embeddings.gte import GTEBase, GTESmall, GTETiny
from ..embeddings.openai import OpenAI
from ..embeddings.palm import PaLM
from ..embeddings.sbert import SBERT
from ..signal import register_signal
from .cluster_hdbscan import ClusterHDBScan
from .concept_labels import ConceptLabelsSignal
from .concept_scorer import ConceptSignal
from .lang_detection import LangDetectionSignal
from .near_dup import NearDuplicateSignal
from .ner import SpacyNER
from .pii import PIISignal
from .text_statistics import TextStatisticsSignal


def register_default_signals() -> None:
  """Register all the default signals."""
  # Concepts.
  register_signal(ConceptSignal)
  register_signal(ConceptLabelsSignal)

  # Text.
  register_signal(PIISignal)
  register_signal(TextStatisticsSignal)
  register_signal(SpacyNER)
  register_signal(NearDuplicateSignal)
  register_signal(LangDetectionSignal)
  register_signal(ClusterHDBScan)

  # Embeddings.
  register_signal(Cohere)
  register_signal(SBERT)
  register_signal(OpenAI)
  register_signal(PaLM)
  register_signal(GTETiny)
  register_signal(GTESmall)
  register_signal(GTEBase)
