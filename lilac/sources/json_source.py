"""JSON source."""
from typing import ClassVar, Iterable, Optional, cast

import duckdb
import pyarrow as pa
from pydantic import Field as PydanticField
from typing_extensions import override

from ..schema import Item, arrow_schema_to_schema
from ..source import Source, SourceSchema
from ..utils import download_http_files
from .duckdb_utils import convert_path_to_duckdb, duckdb_setup


class JSONSource(Source):
  """JSON data loader

  Supports both JSON and JSONL.

  JSON files can live locally as a filepath, point to an external URL, or live on S3, GCS, or R2.

  For more details on authorizing access to S3, GCS or R2, see:
  https://duckdb.org/docs/guides/import/s3_import.html
  """  # noqa: D415, D400

  name: ClassVar[str] = 'json'

  filepaths: list[str] = PydanticField(
    description='A list of filepaths to JSON files. '
    'Paths can be local, point to an HTTP(s) url, or live on GCS, S3 or R2.'
  )

  sample_size: Optional[int] = PydanticField(
    title='Sample size',
    description='Number of rows to sample from the dataset.',
    default=None,
  )

  _source_schema: Optional[SourceSchema] = None
  _reader: Optional[pa.RecordBatchReader] = None
  _con: Optional[duckdb.DuckDBPyConnection] = None

  @override
  def setup(self) -> None:
    # Download JSON files to local cache if they are via HTTP to speed up duckdb.
    filepaths = download_http_files(self.filepaths)
    self._con = duckdb.connect(database=':memory:')
    duckdb_setup(self._con)

    # DuckDB expects s3 protocol: https://duckdb.org/docs/guides/import/s3_import.html.
    duckdb_paths = [convert_path_to_duckdb(path) for path in filepaths]

    # NOTE: We use duckdb here to increase parallelism for multiple files.
    self._con.execute(
      f"""
      CREATE VIEW t as (SELECT * FROM read_json_auto({duckdb_paths}, IGNORE_ERRORS=true));
    """
    )

    res = self._con.execute('SELECT COUNT(*) FROM t').fetchone()
    num_items = cast(tuple[int], res)[0]
    if self.sample_size:
      num_items = min(num_items, self.sample_size)

    if self.sample_size:
      self._reader = self._con.execute(
        f'SELECT * FROM t USING SAMPLE {num_items}'
      ).fetch_record_batch(rows_per_batch=10_000)
    else:
      self._reader = self._con.execute('SELECT * FROM t').fetch_record_batch(rows_per_batch=10_000)
    # Create the source schema in prepare to share it between process and source_schema.
    schema = arrow_schema_to_schema(self._reader.schema)
    self._source_schema = SourceSchema(fields=schema.fields, num_items=num_items)

  @override
  def source_schema(self) -> SourceSchema:
    """Return the source schema."""
    assert self._source_schema is not None, 'setup() must be called first.'
    return self._source_schema

  @override
  def yield_items(self) -> Iterable[Item]:
    """Process the source."""
    if not self._reader or not self._con:
      raise RuntimeError('JSON source is not initialized.')

    for batch in self._reader:
      yield from batch.to_pylist()

    self._reader.close()
    self._con.close()
