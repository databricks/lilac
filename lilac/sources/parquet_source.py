"""Parquet source."""
import random
import urllib.parse
from typing import ClassVar, Iterable, Optional, cast

import duckdb
import pyarrow as pa
from fsspec.core import url_to_fs
from pydantic import Field, field_validator
from typing_extensions import override

from ..schema import Item, Schema, arrow_schema_to_schema
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
  shuffle_between_shards: bool = Field(
    default=False,
    description=
    'If true, the sampling method will stream data from  shards, but not shuffle inside each shard.'
  )

  _source_schema: Optional[SourceSchema] = None
  _readers: list[pa.RecordBatchReader] = []
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

  def _setup_sampling(self, filepaths: list[str]) -> Schema:
    assert self._con, 'setup() must be called first.'
    if self.shuffle_between_shards and self.sample_size:
      # Find the number of files.
      files: list[str] = []
      for filepath in filepaths:
        fs, _ = url_to_fs(filepath)
        scheme = urllib.parse.urlparse(filepath).scheme
        files.extend([f'{scheme}://{file}' for file in fs.glob(filepath)])
      batch_size = max(1, min(self.sample_size // len(files), ROWS_PER_BATCH_READ))
      for file in files:
        duckdb_file = file.replace('gs://', 's3://')
        con = self._con.cursor()
        duckdb_setup(con)
        res = con.execute(f"""SELECT * FROM read_parquet('{duckdb_file}')""")
        self._readers.append(res.fetch_record_batch(rows_per_batch=batch_size))
    else:
      sample_suffix = f'USING SAMPLE {self.sample_size}' if self.sample_size else ''
      duckdb_paths = [path.replace('gs://', 's3://') for path in filepaths]
      res = self._con.execute(f"""SELECT * FROM read_parquet({duckdb_paths}) {sample_suffix}""")
      self._readers.append(res.fetch_record_batch(rows_per_batch=ROWS_PER_BATCH_READ))
    return arrow_schema_to_schema(self._readers[0].schema)

  @override
  def setup(self) -> None:
    filepaths = download_http_files(self.filepaths)
    self._con = duckdb.connect(database=':memory:')
    duckdb_setup(self._con)

    # DuckDB expects s3 protocol: https://duckdb.org/docs/guides/import/s3_import.html.
    duckdb_paths = [path.replace('gs://', 's3://') for path in filepaths]
    res = self._con.execute(f'SELECT COUNT(*) FROM read_parquet({duckdb_paths})').fetchone()
    num_items = cast(tuple[int], res)[0]
    if self.sample_size:
      self.sample_size = min(self.sample_size, num_items)
      num_items = self.sample_size
    schema = self._setup_sampling(filepaths)
    self._source_schema = SourceSchema(fields=schema.fields, num_items=num_items)

  @override
  def source_schema(self) -> SourceSchema:
    """Return the source schema."""
    assert self._source_schema is not None, 'setup() must be called first.'
    return self._source_schema

  @override
  def process(self) -> Iterable[Item]:
    """Process the source."""
    assert self._con, 'setup() must be called first.'

    items_yielded = 0
    done = False
    while not done:
      index = random.randint(0, len(self._readers) - 1)
      reader = self._readers[index]
      batch = None
      try:
        batch = reader.read_next_batch()
      except StopIteration:
        del self._readers[index]
        if not self._readers:
          done = True
          break
        continue
      items = batch.to_pylist()
      for item in items:
        yield item
        items_yielded += 1
        if self.sample_size and items_yielded == self.sample_size:
          done = True
          break

    for reader in self._readers:
      reader.close()
    self._con.close()
