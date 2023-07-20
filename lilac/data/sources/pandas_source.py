"""Pandas source."""
from typing import Any, Iterable

import pandas as pd
from typing_extensions import override

from ...schema import Item
from .source import Source, SourceSchema, schema_from_df

PANDAS_INDEX_COLUMN = '__pd_index__'


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
  def setup(self) -> None:
    # Create the source schema in prepare to share it between process and source_schema.
    self._source_schema = schema_from_df(self._df, PANDAS_INDEX_COLUMN)

  @override
  def source_schema(self) -> SourceSchema:
    """Return the source schema."""
    return self._source_schema

  @override
  def process(self) -> Iterable[Item]:
    """Process the source upload request."""
    cols = self._df.columns.tolist()
    yield from ({
      PANDAS_INDEX_COLUMN: idx,
      **dict(zip(cols, item_vals)),
    } for idx, *item_vals in self._df.itertuples())
