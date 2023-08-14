"""Parquet source."""
from typing import Iterable, Optional

import pyarrow as pa
import pyarrow.parquet as pq
from pydantic import Field
from typing_extensions import override

from ..schema import Item, arrow_schema_to_schema
from .source import Source, SourceSchema


class ParquetSource(Source):
  """Parquet source."""
  name = 'parquet'
  filepaths: list[str] = Field(description='A list of paths to parquet files.')

  _source_schema: Optional[SourceSchema] = None
  _table: Optional[pa.Table] = None

  @override
  def setup(self) -> None:
    assert self.filepaths, 'filepaths must be specified.'
    self._table = pa.concat_tables([pq.read_table(f) for f in self.filepaths])
    self._source_schema = SourceSchema(
      fields=arrow_schema_to_schema(pq.read_schema(self.filepaths[0])).fields,
      num_items=self._table.num_rows)

  @override
  def source_schema(self) -> SourceSchema:
    """Return the source schema."""
    assert self._source_schema is not None, 'setup() must be called first.'
    return self._source_schema

  @override
  def process(self) -> Iterable[Item]:
    """Process the source upload request."""
    assert self._table is not None, 'setup() must be called first.'
    for row in self._table.to_pylist():
      yield row
