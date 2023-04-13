"""Interface for implementing a source."""

import abc
from typing import Any, ClassVar, Optional

from pydantic import BaseModel

from ...schema import ImageInfo, Schema
from ...tasks import TaskId


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
  source_name: str = 'source_base'

  class Config:
    underscore_attrs_are_private = True

  def __init__(self, *args: Any, **kwargs: Any) -> None:
    super().__init__(*args, **kwargs)

    if 'name' not in self.__class__.__dict__:
      raise ValueError('Signal attribute "name" must be defined.')

    self.source_name = self.__class__.name

  @abc.abstractmethod
  def process(
      self,
      output_dir: str,
      task_id: Optional[TaskId] = None,
  ) -> SourceProcessResult:
    """Process the source upload request.

    Args:
      output_dir: The directory to write the output files to.
      shards_loader: The function to use to load the shards. If None, the default shards loader
      task_id: The TaskManager `task_id` for this process run. This is used to update the progress
        of the task.
    """
    pass
