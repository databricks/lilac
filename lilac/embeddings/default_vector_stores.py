"""Registers all vector stores."""
from .vector_store import register_vector_store
from .vector_store_hnsw import HNSWVectorStore
from .vector_store_numpy import NumpyVectorStore


def register_default_vector_stores() -> None:
  """Register all the default vector stores."""
  register_vector_store(HNSWVectorStore)
  register_vector_store(NumpyVectorStore)
