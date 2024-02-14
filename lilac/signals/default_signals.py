"""Registers all available default signals."""

from ..embeddings.bge import BGEM3
from ..embeddings.cohere import Cohere
from ..embeddings.gte import GTEBase, GTESmall, GTETiny
from ..embeddings.jina import JinaV2Base, JinaV2Small
from ..embeddings.nomic_embed import NomicEmbed15, NomicEmbed15_256
from ..embeddings.openai import OpenAIEmbedding
from ..embeddings.sbert import SBERT
from ..signal import register_signal
from .concept_labels import ConceptLabelsSignal
from .concept_scorer import ConceptSignal
from .lang_detection import LangDetectionSignal
from .markdown_code_block import MarkdownCodeBlockSignal
from .near_dup import NearDuplicateSignal
from .ner import SpacyNER
from .pii import PIISignal
from .text_statistics import TextStatisticsSignal


def register_default_signals() -> None:
  """Register all the default signals."""
  # Concepts.
  register_signal(ConceptSignal, exists_ok=True)
  register_signal(ConceptLabelsSignal, exists_ok=True)

  # Text.
  register_signal(PIISignal, exists_ok=True)
  register_signal(TextStatisticsSignal, exists_ok=True)
  register_signal(SpacyNER, exists_ok=True)
  register_signal(NearDuplicateSignal, exists_ok=True)
  register_signal(LangDetectionSignal, exists_ok=True)
  register_signal(MarkdownCodeBlockSignal, exists_ok=True)

  # Embeddings.
  register_signal(Cohere, exists_ok=True)

  register_signal(SBERT, exists_ok=True)

  register_signal(OpenAIEmbedding, exists_ok=True)

  register_signal(GTETiny, exists_ok=True)
  register_signal(GTESmall, exists_ok=True)
  register_signal(GTEBase, exists_ok=True)

  register_signal(JinaV2Small, exists_ok=True)
  register_signal(JinaV2Base, exists_ok=True)

  register_signal(BGEM3, exists_ok=True)
  register_signal(NomicEmbed15, exists_ok=True)
  register_signal(NomicEmbed15_256, exists_ok=True)
