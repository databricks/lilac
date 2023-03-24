"""Interface for splitting individual documents into smaller chunks."""
import abc
from typing import Any, ClassVar

from pydantic import BaseModel

from ..schema import DataType, Field, Item

SPLITS_FEATURE = 'splits'
# These must line up to the pydantic fields in TextSpan.
SPLITS_SPAN_START_FEATURE = 'start'
SPLITS_SPAN_END_FEATURE = 'end'

SPLITS_FIELDS: dict[str, Field] = {
    SPLITS_FEATURE:
        Field(repeated_field=Field(
            fields={
                SPLITS_SPAN_START_FEATURE: Field(dtype=DataType.INT32),
                SPLITS_SPAN_END_FEATURE: Field(dtype=DataType.INT32)
            })),
}


class TextSpan(BaseModel):
  """Represent a span of text with offsets."""
  start: int
  end: int


class TextSplitter(abc.ABC, BaseModel):
  """Interface for splitting documents into smaller chunks."""
  name: ClassVar[str]

  # The splitter_name will get populated in init automatically from the class name so it gets
  # serialized and the signal author doesn't have to define both the static property and the field.
  splitter_name: str = 'splitter_base'

  class Config:
    underscore_attrs_are_private = True

  def __init__(self, *args: Any, **kwargs: Any) -> None:
    super().__init__(*args, **kwargs)

    if 'name' not in self.__class__.__dict__:
      raise ValueError('Splitter attribute "name" must be defined.')

    self.splitter_name = self.__class__.name

  @abc.abstractmethod
  def split(self, text: str) -> list[TextSpan]:
    """Split a document into chunks."""
    pass


def item_from_spans(text_spans: list[TextSpan]) -> Item:
  """Create an item from a list of text spans."""
  return {SPLITS_FEATURE: [split.dict() for split in text_spans]}
