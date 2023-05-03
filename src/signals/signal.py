"""Interface for implementing a signal."""

import abc
from typing import Any, ClassVar, Iterable, Optional, Union

from pydantic import BaseModel, validator

from ..embeddings.embedding_registry import (
    Embedding,
    EmbeddingId,
    get_embedding_cls,
    resolve_embedding,
)
from ..embeddings.vector_store import VectorStore
from ..schema import EnrichmentType, Field, PathTuple, RichData, SignalOut


class Signal(abc.ABC, BaseModel):
  """Interface for signals to implement. A signal can score documents and a dataset column."""
  # ClassVars do not get serialized with pydantic.
  name: ClassVar[str]
  enrichment_type: ClassVar[EnrichmentType]
  vector_based: ClassVar[bool] = False

  # The signal_name will get populated in init automatically from the class name so it gets
  # serialized and the signal author doesn't have to define both the static property and the field.
  signal_name: Optional[str]
  embedding: Optional[EmbeddingId] = None

  class Config:
    underscore_attrs_are_private = True

  _embed_fn: Optional[Embedding] = None

  def __init__(self, *args: Any, **kwargs: Any) -> None:
    super().__init__(*args, **kwargs)

    if self.embedding:
      if isinstance(self.embedding, str):
        self._embed_fn = get_embedding_cls(self.embedding)()
      else:
        self._embed_fn = self.embedding

  @validator('signal_name', pre=True, always=True)
  def validate_signal_name(cls, signal_name: str) -> str:
    """Return the static name when the signal name hasn't yet been set."""
    # When it's already been set from JSON, just return it.
    if signal_name:
      return signal_name

    if 'name' not in cls.__dict__:
      raise ValueError('Signal attribute "name" must be defined.')

    return cls.name

  @validator('embedding', always=True)
  def validate_embedding(cls, embedding: Optional[EmbeddingId]) -> Optional[EmbeddingId]:
    """Return the static name when the signal name hasn't yet been set."""
    if cls.vector_based and not embedding:
      raise ValueError('Signal attribute "embedding" must be defined for "vector_based" signals.')

    return embedding

  @abc.abstractmethod
  def fields(self) -> Field:
    """Return the fields schema for this signal.

    Returns
      A Field object that describes the schema of the signal.
    """
    pass

  def compute(self, data: Iterable[RichData]) -> Iterable[Optional[SignalOut]]:
    """Compute the signal for an iterable of documents or images.

    Args:
      data: An iterable of rich data to compute the signal over.

    Returns
      An iterable of items. Sparse signals should return "None" for skipped inputs.
    """
    raise NotImplementedError

  def vector_compute(self, keys: Iterable[PathTuple],
                     vector_store: VectorStore) -> Iterable[Optional[SignalOut]]:
    """Compute the signal for an iterable of keys that point to documents or images.

    Args:
      keys: An iterable of entity ids (at row-level or lower) to lookup precomputed embeddings.
      vector_store: The vector store to lookup pre-computed embeddings.

    Returns
      An iterable of items. Sparse signals should return "None" for skipped inputs.
    """
    raise NotImplementedError

  def vector_compute_topk(
      self,
      topk: int,
      vector_store: VectorStore,
      keys: Optional[Iterable[PathTuple]] = None) -> list[tuple[PathTuple, Optional[SignalOut]]]:
    """Return signal results only for the top k documents or images.

    Signals decide how to rank each document/image in the dataset, usually by a similarity score
    obtained via the vector store.

    Args:
      topk: The number of items to return, ranked by the signal.
      vector_store: The vector store to lookup pre-computed embeddings.
      keys: Optional iterable of row ids to restrict the search to.

    Returns
      A list of (key, signal_output) tuples containing the "topk" items. Sparse signals should
      return "None" for skipped inputs.
    """
    raise NotImplementedError

  @validator('embedding', pre=True)
  def parse_embedding(cls, embedding: Union[dict, str]) -> EmbeddingId:
    """Parse an embedding to its specific subclass instance."""
    if embedding is None:
      return embedding
    if isinstance(embedding, str):
      return embedding
    return resolve_embedding(embedding)

  def key(self) -> str:
    """Get the key for a signal.

    This is used to make sure signals with multiple arguments do not collide.

    NOTE: Overriding this method is sensitive. If you override it, make sure that it is globally
    unique. It will be used as the dictionary key for enriched values.
    """
    args_dict = self.dict(exclude_unset=True)
    # If a user explicitly defines a signal name for whatever reason, remove it as it's redundant.
    if 'signal_name' in args_dict:
      del args_dict['signal_name']
    args = None
    args_list: list[str] = []
    for k, v in args_dict.items():
      if v:
        args_list.append(f'{k}={v}')

    args = ','.join(args_list)
    display_args = '' if not args_list else f'({args})'
    return self.name + display_args
