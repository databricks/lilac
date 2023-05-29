"""CSV source."""
from typing import Iterable, Optional

import duckdb
from pydantic import Field
from typing_extensions import override

from ...schema import Item
from ...utils import download_http_files
from ..duckdb_utils import duckdb_gcs_setup
from .pandas_source import PandasDataset
from .source import Source, SourceSchema


class CSVDataset(Source):
  """CSV data loader

  CSV files can live locally as a filepath, or point to an external URL.
  """ # noqa: D415, D400
  name = 'csv'

  filepaths: list[str] = Field(description='A list of filepaths to CSV files.')
  delim: Optional[str] = Field(default=',', description='The CSV file delimiter to use.')

  _source_schema: SourceSchema
  _pd_source: PandasDataset

  @override
  def prepare(self) -> None:
    # Download CSV files to /tmp if they are via HTTP to speed up duckdb.
    filepaths = download_http_files(self.filepaths)

    con = duckdb.connect(database=':memory:')

    # DuckDB expects s3 protocol: https://duckdb.org/docs/guides/import/s3_import.html.
    s3_filepaths = [path.replace('gs://', 's3://') for path in filepaths]

    # NOTE: We use duckdb here to increase parallelism for multiple files.
    df = con.execute(f"""
      {duckdb_gcs_setup(con)}
      SELECT * FROM read_csv_auto(
        {s3_filepaths},
        SAMPLE_SIZE=500000,
        DELIM='{self.delim or ','}',
        IGNORE_ERRORS=true
    )
    """).fetchdf()

    self._pd_source = PandasDataset(df=df)
    self._pd_source.prepare()

  @override
  def source_schema(self) -> SourceSchema:
    """Return the source schema."""
    return self._pd_source.source_schema()

  @override
  def process(self) -> Iterable[Item]:
    """Process the source upload request."""
    return self._pd_source.process()
