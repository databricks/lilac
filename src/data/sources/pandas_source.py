"""Pandas source."""
import math
from typing import Any, Iterable

import pandas as pd
import pyarrow as pa
from typing_extensions import override

from ...schema import UUID_COLUMN, DataType, Item, arrow_schema_to_schema, field
from .source import Source, SourceSchema


class PandasDataset(Source):
  """Pandas source."""
  name = 'pandas'

  _df: pd.DataFrame
  _source_schema: SourceSchema

  class Config:
    underscore_attrs_are_private = True

  def __init__(self, df: pd.DataFrame, **kwargs: Any):
    super().__init__(**kwargs)
    self._df = df

  @override
  def prepare(self) -> None:
    # Create the source schema in prepare to share it between process and source_schema.
    schema = arrow_schema_to_schema(pa.Schema.from_pandas(self._df, preserve_index=False))
    self._source_schema = SourceSchema(
      fields={
        **schema.fields, UUID_COLUMN: field('string')
      }, num_items=len(self._df))

  @override
  def source_schema(self) -> SourceSchema:
    """Return the source schema."""
    return self._source_schema

  @override
  def process(self) -> Iterable[Item]:
    """Process the source upload request."""
    fields = self._source_schema.fields
    string_fields = {
      name: field for name, field in fields.items() if field.dtype == DataType.STRING
    }
    timestamp_fields = {
      name: field for name, field in fields.items() if field.dtype == DataType.TIMESTAMP
    }
    for idx, item in self._df.to_dict(orient='index').items():
      # Add row id if it doesn't exist. Use the index from the series.
      if UUID_COLUMN not in item:
        item[UUID_COLUMN] = idx

      # Fix NaN string fields.
      for name in string_fields.keys():
        item_value = item[name]
        if not isinstance(item_value, str):
          if math.isnan(item_value):
            item[name] = None
          else:
            item[name] = str(item_value)

      # Fix NaT (not a time) timestamp fields.
      for name in timestamp_fields.keys():
        item_value = item[name]
        if pd.isnull(item_value):
          item[name] = None

      yield item
