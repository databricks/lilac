"""Interface for implementing a source."""

import abc
from typing import ClassVar, Iterable, Optional

from pydantic import BaseModel, validator

from ...schema import Field, ImageInfo, Item, Schema


class SourceSchema(BaseModel):
  """The schema of a source."""
  fields: dict[str, Field]
  num_items: Optional[int]


class SourceProcessResult(BaseModel):
  """The result after processing all the shards of a source dataset."""
  filepaths: list[str]
  data_schema: Schema
  images: Optional[list[ImageInfo]]
  num_items: int


class Source(abc.ABC, BaseModel):
  """Interface for sources to implement. A source processes a set of shards and writes files."""
  # ClassVars do not get serialized with pydantic.
  name: ClassVar[str]

  # The source_name will get populated in init automatically from the class name so it gets
  # serialized and the source author doesn't have to define both the static property and the field.
  source_name: Optional[str]

  class Config:
    underscore_attrs_are_private = True

  @validator('source_name', always=True)
  def validate_source_name(cls, source_name: str) -> str:
    """Return the static name when the source_name name hasn't yet been set."""
    # When it's already been set from JSON, just return it.
    if source_name:
      return source_name

    if 'name' not in cls.__dict__:
      raise ValueError('Source attribute "name" must be defined.')

    return cls.name

  @abc.abstractmethod
  def source_schema(self) -> SourceSchema:
    """Return the source schema for this source.

    Returns
      A SourceSchema with
        fields: mapping top-level columns to fields that describes the schema of the source.
        num_items: the number of items in the source, used for progress.

    """
    pass

  def prepare(self) -> None:
    """Prepare the source.

    This allows the source to do setup outside the constructor, but before its processed. This
    avoids potentially expensive computation the pydantic model is deserialized.
    """
    pass

  @abc.abstractmethod
  def process(self) -> Iterable[Item]:
    """Process the source upload request.

    Args:
      task_step_id: The TaskManager `task_step_id` for this process run. This is used to update the
        progress of the task.
    """
    pass
