"""Interface for implementing a source."""

from typing import TYPE_CHECKING, Any, Callable, ClassVar, Iterable, Optional, Type

import numpy as np
import pandas as pd
import pyarrow as pa
from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, model_serializer

if TYPE_CHECKING:
  pass

from .schema import (
  Field,
  ImageInfo,
  Item,
  Schema,
  arrow_dtype_to_dtype,
  arrow_schema_to_schema,
  field,
)


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

    Returns
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

  def process(self) -> Iterable[Item]:
    """Process the source upload request.

    Args:
      task_step_id: The TaskManager `task_step_id` for this process run. This is used to update the
        progress of the task.
    """
    raise NotImplementedError


def schema_from_df(df: pd.DataFrame, index_colname: str) -> SourceSchema:
  """Create a source schema from a dataframe."""
  index_np_dtype = df.index.dtype
  # String index dtypes are stored as objects.
  if index_np_dtype == np.dtype(object):
    index_np_dtype = np.dtype(str)
  index_dtype = arrow_dtype_to_dtype(pa.from_numpy_dtype(index_np_dtype))

  schema = arrow_schema_to_schema(pa.Schema.from_pandas(df, preserve_index=False))
  return SourceSchema(
    fields={
      **schema.fields, index_colname: field(dtype=index_dtype)
    }, num_items=len(df))
