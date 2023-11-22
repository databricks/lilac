"""Parquet source."""
import os
import random
from typing import ClassVar, Optional, cast

import duckdb
import pyarrow as pa
from pydantic import Field, ValidationInfo, field_validator
from typing_extensions import override

from ..data import dataset_utils
from ..schema import PARQUET_FILENAME_PREFIX, ROWID, Schema, arrow_schema_to_schema
from ..source import Source, SourceManifest, SourceSchema
from ..sources.duckdb_utils import convert_path_to_duckdb, duckdb_setup
from ..tasks import TaskStepId
from ..utils import download_http_files

# Number of rows to read per batch.
ROWS_PER_BATCH_READ = 50_000


class ParquetSource(Source):
  """Parquet data loader

  Parquet files can live locally as a filepath, or remotely on GCS, S3, or Hadoop.

  For more details on authentication with private objects, see:
  https://arrow.apache.org/docs/python/filesystems.html
  """  # noqa: D415, D400

  name: ClassVar[str] = 'parquet'
  filepaths: list[str] = Field(
    description='A list of paths to parquet files which live locally or remotely on GCS, S3, or '
    'Hadoop.'
  )
  seed: Optional[int] = Field(description='Random seed for sampling', default=None)
  sample_size: Optional[int] = Field(
    title='Sample size', description='Number of rows to sample from the dataset', default=None
  )
  pseudo_shuffle: bool = Field(
    default=False,
    description='If true, the reader will read a fraction of rows from each shard, '
    'avoiding a pass over the entire dataset.',
  )
  pseudo_shuffle_num_shards: int = Field(
    default=10, description='Number of shards to sample from when using pseudo shuffle.'
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
  def validate_sample_size(cls, sample_size: Optional[int]) -> Optional[int]:
    """Validate sample size."""
    if sample_size is not None and sample_size < 1:
      raise ValueError('sample_size must be greater than 0.')
    return sample_size

  @field_validator('pseudo_shuffle')
  @classmethod
  def validate_pseudo_shuffle(cls, pseudo_shuffle: bool, info: ValidationInfo) -> bool:
    """Validate shuffle before sampling."""
    if pseudo_shuffle and not info.data['sample_size']:
      raise ValueError('`pseudo_shuffle` requires `sample_size` to be set.')
    return pseudo_shuffle

  def _setup_sampling(self, duckdb_paths: list[str]) -> None:
    assert self._con, 'setup() must be called first.'
    if self.pseudo_shuffle:
      assert self.sample_size, 'pseudo_shuffle requires sample_size to be set.'
      # Resolve globs into individual files.
      glob_rows: list[tuple[str]] = self._con.execute(
        f'SELECT * FROM GLOB({duckdb_paths})'
      ).fetchall()
      duckdb_files: list[str] = list(set([row[0] for row in glob_rows]))
      # Sub-sample shards so we don't open too many files.
      num_shards = min(self.pseudo_shuffle_num_shards, len(duckdb_files))
      # The 1.5 multiplier gives some wiggle room for heterogeneous shard sizes, in case one shard
      # fails to yield as many samples as hoped.
      samples_per_shard = max(1, int((self.sample_size * 1.5) // num_shards))
      duckdb_files = random.sample(duckdb_files, num_shards)
      self._duckdb_files = duckdb_files

      shard_query = '\nUNION ALL\n'.join(
        f'(SELECT * FROM read_parquet("{path}") LIMIT {samples_per_shard})' for path in duckdb_files
      )
      self._process_query = f"""
          SELECT replace(CAST(uuid() AS VARCHAR), '-', '') AS {ROWID}, *
          FROM ({shard_query}) LIMIT {self.sample_size}"""
    else:
      sample_suffix = ''
      if self.sample_size:
        sample_suffix = f'USING SAMPLE {self.sample_size}'
        if self.seed is not None:
          sample_suffix += f' (reservoir, {self.seed})'
      self._process_query = f"""
          SELECT replace(CAST(uuid() AS VARCHAR), '-', '') AS {ROWID},
              * FROM read_parquet({duckdb_paths}) {sample_suffix}"""

  @override
  def setup(self) -> None:
    filepaths = download_http_files(self.filepaths)
    self._con = duckdb.connect(database=':memory:')
    duckdb_setup(self._con)

    # DuckDB expects s3 protocol: https://duckdb.org/docs/guides/import/s3_import.html.
    duckdb_paths = [convert_path_to_duckdb(path) for path in filepaths]
    res = self._con.execute(f'SELECT COUNT(*) FROM read_parquet({duckdb_paths})').fetchone()
    num_items = cast(tuple[int], res)[0]
    if self.sample_size:
      self.sample_size = min(self.sample_size, num_items)
      num_items = self.sample_size
    schema = arrow_schema_to_schema(
      self._con.execute(f"""SELECT * FROM read_parquet('{duckdb_paths[0]}')""")
      .fetch_record_batch(1)
      .schema
    )
    self._source_schema = SourceSchema(fields=schema.fields, num_items=num_items)
    self._setup_sampling(duckdb_paths)

  @override
  def source_schema(self) -> SourceSchema:
    """Return the source schema."""
    assert self._source_schema is not None, 'setup() must be called first.'
    return self._source_schema

  @override
  def load_to_parquet(
    self, output_dir: str, task_step_id: Optional[TaskStepId] = None
  ) -> SourceManifest:
    del task_step_id

    assert self._con, 'setup() must be called first.'

    out_filename = dataset_utils.get_parquet_filename(PARQUET_FILENAME_PREFIX, 0, 1)
    filepath = os.path.join(output_dir, out_filename)
    os.makedirs(output_dir, exist_ok=True)

    self._con.sql(self._process_query).write_parquet(filepath, compression='zstd')
    schema = Schema(fields=self.source_schema().fields.copy())
    return SourceManifest(files=[out_filename], data_schema=schema, source=self)
