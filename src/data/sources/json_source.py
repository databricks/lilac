"""CSV source."""
from typing import Iterable

import duckdb
from pydantic import Field as PydanticField
from typing_extensions import override

from ...schema import Item
from ...utils import download_http_files
from ..duckdb_utils import duckdb_gcs_setup
from .pandas_source import PandasDataset
from .source import Source, SourceSchema


class JSONDataset(Source):
  """JSON data loader

  Supports both JSON and JSONL.

  JSON files can live locally as a filepath, or point to an external URL.
  """ # noqa: D415, D400
  name = 'json'

  filepaths: list[str] = PydanticField(description='A list of filepaths to JSON files.')

  _source_schema: SourceSchema
  _pd_source: PandasDataset

  @override
  def prepare(self) -> None:
    # Download JSON files to local cache if they are via HTTP to speed up duckdb.
    filepaths = download_http_files(self.filepaths)

    con = duckdb.connect(database=':memory:')

    # DuckDB expects s3 protocol: https://duckdb.org/docs/guides/import/s3_import.html.
    s3_filepaths = [path.replace('gs://', 's3://') for path in filepaths]

    # NOTE: We use duckdb here to increase parallelism for multiple files.
    df = con.execute(f"""
      {duckdb_gcs_setup(con)}
      SELECT * FROM read_json_auto(
        {s3_filepaths},
        IGNORE_ERRORS=true
      )
    """).df()

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
