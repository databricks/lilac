"""Default embeddings registered in the global registry."""

from .cohere import Cohere
from .embedding_registry import register_embedding


def register_default_embeddings() -> None:
  """Register all the default embedding functions."""
  register_embedding(Cohere)
