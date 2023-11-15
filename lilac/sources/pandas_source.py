"""Pandas source."""
from typing import Any, ClassVar, Iterable, Optional

import pandas as pd
from typing_extensions import override

from ..schema import Item
from ..source import Source, SourceSchema, schema_from_df

PANDAS_INDEX_COLUMN = '__pd_index__'


class PandasSource(Source):
  """Pandas source."""

  name: ClassVar[str] = 'pandas'

  _df: Optional[pd.DataFrame] = None
  _source_schema: SourceSchema

  def __init__(self, df: Optional[pd.DataFrame] = None, **kwargs: Any):
    super().__init__(**kwargs)
    self._df = df

  @override
  def setup(self) -> None:
    assert self._df is not None, 'df must be set.'
    # Create the source schema in prepare to share it between process and source_schema.
    self._source_schema = schema_from_df(self._df, PANDAS_INDEX_COLUMN)

  @override
  def source_schema(self) -> SourceSchema:
    """Return the source schema."""
    return self._source_schema

  @override
  def yield_items(self) -> Iterable[Item]:
    """Process the source."""
    assert self._df is not None, 'df must be set.'
    cols = self._df.columns.tolist()
    yield from (
      {PANDAS_INDEX_COLUMN: idx, **dict(zip(cols, item_vals))}
      for idx, *item_vals in self._df.itertuples()
    )
