"""Interface for implementing a source."""

from typing import TYPE_CHECKING, Any, ClassVar, Iterable, Optional, Type, Union

import numpy as np
import pandas as pd
import pyarrow as pa
from pydantic import BaseModel

if TYPE_CHECKING:
  from pydantic.typing import AbstractSetIntStr, MappingIntStrAny

from ..schema import (
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


class Source(BaseModel):
  """Interface for sources to implement. A source processes a set of shards and writes files."""
  # ClassVars do not get serialized with pydantic.
  name: ClassVar[str]

  def dict(
    self,
    *,
    include: Optional[Union['AbstractSetIntStr', 'MappingIntStrAny']] = None,
    exclude: Optional[Union['AbstractSetIntStr', 'MappingIntStrAny']] = None,
    by_alias: bool = False,
    skip_defaults: Optional[bool] = None,
    exclude_unset: bool = False,
    exclude_defaults: bool = False,
    exclude_none: bool = False,
  ) -> dict[str, Any]:
    """Override the default dict method to add `source_name`."""
    res = super().dict(
      include=include,
      exclude=exclude,
      by_alias=by_alias,
      skip_defaults=skip_defaults,
      exclude_unset=exclude_unset,
      exclude_defaults=exclude_defaults,
      exclude_none=exclude_none)
    res['source_name'] = self.name
    return res

  class Config:
    underscore_attrs_are_private = True

    @staticmethod
    def schema_extra(schema: dict[str, Any], source: Type['Source']) -> None:
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


def normalize_column_name(name: str) -> str:
  """Normalize a column name."""
  return name
  #return name.replace(' ', '_').replace(':', '_').replace('.', '_')
