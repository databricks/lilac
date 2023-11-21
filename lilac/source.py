"""Interface for implementing a source."""

from typing import Any, Callable, ClassVar, Iterable, Optional, Type, Union

import numpy as np
import pandas as pd
import pyarrow as pa
from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, SerializeAsAny, field_validator, model_serializer

from .schema import (
  Field,
  ImageInfo,
  Item,
  Schema,
  arrow_dtype_to_dtype,
  arrow_schema_to_schema,
  field,
)
from .tasks import TaskStepId


class SourceSchema(BaseModel):
  """The schema of a source."""

  fields: dict[str, Field]
  num_items: Optional[int] = None


class SourceProcessResult(BaseModel):
  """The result after processing all the shards of a source dataset."""

  filepaths: list[str]
  data_schema: Schema
  num_items: int
  images: Optional[list[ImageInfo]] = None


def _source_schema_extra(schema: dict[str, Any], source: Type['Source']) -> None:
  """Add the title to the schema from the display name and name.

  Pydantic defaults this to the class name.
  """
  signal_prop: dict[str, Any]
  if hasattr(source, 'name'):
    signal_prop = {'enum': [source.name]}
  else:
    signal_prop = {'type': 'string'}
  schema['properties'] = {'source_name': signal_prop, **schema['properties']}
  if 'required' not in schema:
    schema['required'] = []
  schema['required'].append('source_name')


class Source(BaseModel):
  """Interface for sources to implement. A source processes a set of shards and writes files."""

  # ClassVars do not get serialized with pydantic.
  name: ClassVar[str]
  router: ClassVar[Optional[APIRouter]] = None

  @model_serializer(mode='wrap')
  def serialize_model(self, serializer: Callable[..., dict[str, Any]]) -> dict[str, Any]:
    """Serialize the model to a dictionary."""
    res = serializer(self)
    res['source_name'] = self.name
    return res

  model_config = ConfigDict(json_schema_extra=_source_schema_extra)

  def source_schema(self) -> SourceSchema:
    """Return the source schema for this source.

    Returns:
      A SourceSchema with
        fields: mapping top-level columns to fields that describes the schema of the source.
        num_items: the number of items in the source, used for progress.

    """
    raise NotImplementedError

  def setup(self) -> None:
    """Prepare the source for processing.

    This allows the source to do setup outside the constructor, but before its processed. This
    avoids potentially expensive computation the pydantic model is deserialized.
    """
    pass

  def teardown(self) -> None:
    """Tears down the source after processing."""
    pass

  def yield_items(self) -> Iterable[Item]:
    """Process the source by yielding individual rows of the source data.

    You should only override one of `yield_items` or `load_to_parquet`.

    This method is easier to use, and simply requires you to return an iterator of Python dicts.
    Lilac will take your iterable of items and handle writing it to parquet. You will still have to
    override source_schema.

    Args:
      task_step_id: The TaskManager `task_step_id` for this process run. This is used to update the
        progress of the task.
    """
    raise NotImplementedError

  def load_to_parquet(
    self, output_dir: str, task_step_id: Optional[TaskStepId]
  ) -> 'SourceManifest':
    """Process the source by directly writing a parquet file.

    You should only override one of `yield_items` or `load_to_parquet`.

    This fast path exists for sources where we are able to avoid the overhead of creating python
    dicts for every row by using non-Python parquet writers like DuckDB.

    The output parquet files should have a {schema.ROWID} column defined. This ROWID should not be
    part of source_schema, however.

    Args:
      output_dir: The directory to write the parquet files to.
      task_step_id: The TaskManager `task_step_id` for this process run. This is used to update the
        progress of the task.

    Returns:
      A SourceManifest that describes schema and parquet file locations.
    """
    raise NotImplementedError


class NoSource(Source):
  """A dummy source that is used when no source is defined, for backwards compat."""

  name: ClassVar[str] = 'no_source'


class SourceManifest(BaseModel):
  """The raw dataset contents, converted to Parquet, prior to any Lilac-specific annotations."""

  model_config = ConfigDict(strict=False)

  # List of a parquet filepaths storing the data. The paths can be relative to `manifest.json`.
  files: list[str]
  # The data schema.
  data_schema: Schema
  source: SerializeAsAny[Source] = NoSource()

  # Image information for the dataset.
  images: Optional[list[ImageInfo]] = None

  @field_validator('source', mode='before')
  @classmethod
  def parse_source(cls, source: dict) -> Source:
    """Parse a source to its specific subclass instance."""
    return resolve_source(source)


def schema_from_df(df: pd.DataFrame, index_colname: str) -> SourceSchema:
  """Create a source schema from a dataframe."""
  index_np_dtype = df.index.dtype
  # String index dtypes are stored as objects.
  if index_np_dtype == np.dtype(object):
    index_np_dtype = np.dtype(str)
  index_dtype = arrow_dtype_to_dtype(pa.from_numpy_dtype(index_np_dtype))

  schema = arrow_schema_to_schema(pa.Schema.from_pandas(df, preserve_index=False))
  return SourceSchema(
    fields={**schema.fields, index_colname: field(dtype=index_dtype)}, num_items=len(df)
  )


SOURCE_REGISTRY: dict[str, Type[Source]] = {}


def register_source(source_cls: Type[Source]) -> None:
  """Register a source configuration globally."""
  if source_cls.name in SOURCE_REGISTRY:
    raise ValueError(f'Source "{source_cls.name}" has already been registered!')

  SOURCE_REGISTRY[source_cls.name] = source_cls


def get_source_cls(source_name: str) -> Optional[Type[Source]]:
  """Return a registered source given the name in the registry."""
  return SOURCE_REGISTRY.get(source_name)


def registered_sources() -> dict[str, Type[Source]]:
  """Return all registered sources."""
  return SOURCE_REGISTRY


def resolve_source(source: Union[dict, Source]) -> Source:
  """Resolve a generic source base class to a specific source class."""
  if isinstance(source, Source):
    # The source is already parsed.
    return source

  source_name = source.get('source_name')
  if not source_name:
    raise ValueError('"source_name" needs to be defined in the json dict.')

  source_cls = get_source_cls(source_name)
  if not source_cls:
    # Make a metaclass so we get a valid `Source` class.
    source_cls = type(f'Source_{source_name}', (Source,), {'name': source_name})
  return source_cls(**source)


def clear_source_registry() -> None:
  """Clear the source registry."""
  SOURCE_REGISTRY.clear()
