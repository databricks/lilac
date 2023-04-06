"""Interface for implementing a source."""

import abc
from typing import Any, Awaitable, Callable, ClassVar, Generic, Optional, Type, TypeVar

from pydantic import BaseModel

from ...schema import ImageInfo, Schema


class SourceShardOut(BaseModel):
  """The result of a single shard of a source dataset."""
  filepath: str
  num_items: int


BaseShardInfo = TypeVar('BaseShardInfo', bound=BaseModel)

# Loads an input shard and returns the output of `process_shard`.
ShardsLoader = Callable[[list[BaseShardInfo]], Awaitable[list[SourceShardOut]]]


class SourceProcessResult(BaseModel):
  """The result after processing all the shards of a source dataset."""
  filepaths: list[str]
  data_schema: Schema
  images: Optional[list[ImageInfo]]
  num_items: int


class Source(abc.ABC, BaseModel, Generic[BaseShardInfo]):
  """Interface for sources to implement. A source processes a set of shards and writes files."""
  # ClassVars do not get serialized with pydantic.
  name: ClassVar[str]
  shard_info_cls: ClassVar[Type[BaseModel]]

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
  async def process(self,
                    output_dir: str,
                    shards_loader: Optional[ShardsLoader] = None) -> SourceProcessResult:
    """Process the source upload request.

    Args:
      output_dir: The directory to write the output files to.
      shards_loader: The function to use to load the shards. If None, the default shards loader
    """
    pass

  @abc.abstractmethod
  def process_shard(self, shard_info: BaseShardInfo) -> SourceShardOut:
    """Process an individual file shard from an input dataset."""
    pass


def default_shards_loader(source: Source) -> ShardsLoader:
  """Default shards loader that just calls process_shard on each shard."""

  async def shards_loader(shard_infos: list[BaseShardInfo]) -> list[SourceShardOut]:
    return [source.process_shard(x) for x in shard_infos]

  return shards_loader
