"""Parquet source."""
from typing import ClassVar, Iterable, Optional, cast

import duckdb
import pyarrow as pa
from pydantic import Field, field_validator
from typing_extensions import override

from ..schema import Item, arrow_schema_to_schema
from ..source import Source, SourceSchema
from ..sources.duckdb_utils import duckdb_setup
from ..utils import download_http_files

# Number of rows to read per batch.
ROWS_PER_BATCH_READ = 10_000


class ParquetSource(Source):
  """Parquet data loader

  Parquet files can live locally as a filepath, or remotely on GCS, S3, or Hadoop.

  For more details on authentication with private objects, see:
  https://arrow.apache.org/docs/python/filesystems.html
  """ # noqa: D415, D400
  name: ClassVar[str] = 'parquet'
  filepaths: list[str] = Field(
    description=
    'A list of paths to parquet files which live locally or remotely on GCS, S3, or Hadoop.')
  sample_size: Optional[int] = Field(
    title='Sample size', description='Number of rows to sample from the dataset', default=None)

  _source_schema: Optional[SourceSchema] = None
  _reader: Optional[pa.RecordBatchReader] = None
  _con: Optional[duckdb.DuckDBPyConnection] = None

  @field_validator('filepaths')
  @classmethod
  def validate_filepaths(cls, filepaths: list[str]) -> list[str]:
    """Validate filepaths."""
    if not filepaths:
      raise ValueError('filepaths must be non-empty.')
    return filepaths

  @field_validator('sample_size')
  @classmethod
  def validate_sample_size(cls, sample_size: int) -> int:
    """Validate sample size."""
    if sample_size < 1:
      raise ValueError('sample_size must be greater than 0.')
    return sample_size

  @override
  def setup(self) -> None:
    filepaths = download_http_files(self.filepaths)
    self._con = duckdb.connect(database=':memory:')
    duckdb_setup(self._con)

    # DuckDB expects s3 protocol: https://duckdb.org/docs/guides/import/s3_import.html.
    s3_filepaths = [path.replace('gs://', 's3://') for path in filepaths]

    # NOTE: We use duckdb here to increase parallelism for multiple files.
    sample_suffix = f'USING SAMPLE {self.sample_size}' if self.sample_size else ''
    self._con.execute(f"""
      CREATE VIEW t as (SELECT * FROM read_parquet({s3_filepaths}) {sample_suffix});
    """)
    res = self._con.execute('SELECT COUNT(*) FROM t').fetchone()
    num_items = cast(tuple[int], res)[0]
    self._reader = self._con.execute('SELECT * from t').fetch_record_batch(
      rows_per_batch=ROWS_PER_BATCH_READ)
    # Create the source schema in prepare to share it between process and source_schema.
    schema = arrow_schema_to_schema(self._reader.schema)
    self._source_schema = SourceSchema(fields=schema.fields, num_items=num_items)

  @override
  def source_schema(self) -> SourceSchema:
    """Return the source schema."""
    assert self._source_schema is not None, 'setup() must be called first.'
    return self._source_schema

  @override
  def process(self) -> Iterable[Item]:
    """Process the source."""
    assert self._reader and self._con, 'setup() must be called first.'

    for batch in self._reader:
      yield from batch.to_pylist()

    self._reader.close()
    self._con.close()
