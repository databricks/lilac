"""CSV source."""
from typing import Iterable, Optional

import duckdb
import pandas as pd
from pydantic import Field
from typing_extensions import override

from ..schema import Item
from ..utils import download_http_files
from .duckdb_utils import duckdb_setup
from .source import Source, SourceSchema, normalize_column_name, schema_from_df

LINE_NUMBER_COLUMN = '__line_number__'


class CSVSource(Source):
  """CSV data loader

  CSV files can live locally as a filepath, or point to an external URL.
  """ # noqa: D415, D400
  name = 'csv'

  filepaths: list[str] = Field(description='A list of paths to CSV files.')
  delim: Optional[str] = Field(default=',', description='The CSV file delimiter to use.')
  header: Optional[bool] = Field(default=True, description='Whether the CSV file has a header row.')
  names: Optional[list[str]] = Field(
    default=None, description='Provide header names if the file does not contain a header.')

  _source_schema: Optional[SourceSchema] = None
  _df: Optional[pd.DataFrame] = None

  @override
  def setup(self) -> None:
    # Download CSV files to /tmp if they are via HTTP to speed up duckdb.
    filepaths = download_http_files(self.filepaths)

    con = duckdb.connect(database=':memory:')

    # DuckDB expects s3 protocol: https://duckdb.org/docs/guides/import/s3_import.html.
    s3_filepaths = [path.replace('gs://', 's3://') for path in filepaths]

    # NOTE: We use duckdb here to increase parallelism for multiple files.
    # NOTE: We turn off the parallel reader because of https://github.com/lilacai/lilac/issues/373.
    self._df = con.execute(f"""
      {duckdb_setup(con)}
      SELECT * FROM read_csv_auto(
        {s3_filepaths},
        SAMPLE_SIZE=500000,
        HEADER={self.header},
        {f'NAMES={self.names},' if self.names else ''}
        DELIM='{self.delim or ','}',
        IGNORE_ERRORS=true,
        PARALLEL=false
    )
    """).df()
    for column_name in self._df.columns:
      self._df.rename(columns={column_name: normalize_column_name(column_name)}, inplace=True)

    # Create the source schema in prepare to share it between process and source_schema.
    self._source_schema = schema_from_df(self._df, LINE_NUMBER_COLUMN)

  @override
  def source_schema(self) -> SourceSchema:
    """Return the source schema."""
    assert self._source_schema is not None
    return self._source_schema

  @override
  def process(self) -> Iterable[Item]:
    """Process the source upload request."""
    if self._df is None:
      raise RuntimeError('CSV source is not initialized.')

    cols = self._df.columns.tolist()
    yield from ({
      LINE_NUMBER_COLUMN: idx,
      **dict(zip(cols, item_vals)),
    } for idx, *item_vals in self._df.itertuples())
