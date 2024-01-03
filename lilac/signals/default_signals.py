"""Registers all available default signals."""
import modal.config

from ..embeddings.cohere import Cohere
from ..embeddings.gte import GTEBase, GTESmall, GTETiny
from ..embeddings.jina import JinaV2Base, JinaV2Small
from ..embeddings.jina_garden import JinaV2SmallGarden
from ..embeddings.openai import OpenAIEmbedding
from ..embeddings.palm import PaLM
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


def has_garden_credentials() -> bool:
  """Returns whether the user has Garden credentials."""
  config = modal.config.Config().to_dict()
  return 'token_secret' in config and 'token_id' in config


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
  register_signal(MarkdownCodeBlockSignal)

  # Embeddings.
  register_signal(Cohere)

  register_signal(SBERT)

  register_signal(OpenAIEmbedding)

  register_signal(PaLM)

  register_signal(GTETiny)
  register_signal(GTESmall)
  register_signal(GTEBase)

  register_signal(JinaV2Small)
  register_signal(JinaV2Base)

  if has_garden_credentials():
    register_signal(JinaV2SmallGarden)
