"""Embeddings compute a vector for a chunk of a document."""

from .default_vector_stores import register_default_vector_stores
from .embedding import compute_split_embeddings

register_default_vector_stores()

__all__ = ['compute_split_embeddings']
