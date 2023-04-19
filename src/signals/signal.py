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
from ..schema import EnrichmentType, Field, Path, RichData, SignalOut


class Signal(abc.ABC, BaseModel):
  """Interface for signals to implement. A signal can score documents and a dataset column."""
  # ClassVars do not get serialized with pydantic.
  name: ClassVar[str]
  enrichment_type: ClassVar[EnrichmentType]
  embedding_based: ClassVar[bool] = False

  # The signal_name will get populated in init automatically from the class name so it gets
  # serialized and the signal author doesn't have to define both the static property and the field.
  signal_name: str = 'signal_base'
  embedding: Optional[EmbeddingId] = None

  class Config:
    underscore_attrs_are_private = True

  _embed_fn: Optional[Embedding] = None

  def __init__(self, *args: Any, **kwargs: Any) -> None:
    super().__init__(*args, **kwargs)

    if 'name' not in self.__class__.__dict__:
      raise ValueError('Signal attribute "name" must be defined.')

    if self.__class__.embedding_based and not self.embedding:
      raise ValueError(
          'Signal attribute "embedding" must be defined for "embedding_based" signals.')

    if self.embedding:
      if isinstance(self.embedding, str):
        self._embed_fn = get_embedding_cls(self.embedding)()
      else:
        self._embed_fn = self.embedding

    self.signal_name = self.__class__.name

  @abc.abstractmethod
  def fields(self, input_column: Path) -> Field:
    """Return the fields schema for this signal.

    Args:
      input_column: The input column path that the signal is being applied to. This is useful for
        fields that are references (Field.refers_to) to other fields, like a STRING_SPAN.

    Returns
      A Field object that describes the schema of the signal.
    """
    pass

  @abc.abstractmethod
  def compute(self,
              data: Optional[Iterable[RichData]] = None,
              keys: Optional[Iterable[str]] = None,
              vector_store: Optional[VectorStore] = None) -> Iterable[Optional[SignalOut]]:
    """Compute the signal for an iterable of row-keyed documents or images.

    Args:
      data: An iterable of rich data to compute the signal over
      keys: An iterable of row-uuids. These are used to lookup pre-computed embeddings.
      vector_store: The vector store to lookup pre-computed embeddings.

    Returns
      An iterable of items. The signal should return "None" if the signal is sparse for the input.
    """
    pass

  @validator('embedding', pre=True)
  def parse_embedding(cls, embedding: Union[dict, str]) -> EmbeddingId:
    """Parse an embedding to its specific subclass instance."""
    if embedding is None:
      return embedding
    if isinstance(embedding, str):
      return embedding
    return resolve_embedding(embedding)
