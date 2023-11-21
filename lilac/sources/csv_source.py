"""CSV source."""
import os
from typing import ClassVar, Optional, cast

import duckdb
import pyarrow as pa
from pydantic import Field
from typing_extensions import override

from ..data import dataset_utils
from ..schema import PARQUET_FILENAME_PREFIX, ROWID, Schema, arrow_schema_to_schema
from ..source import Source, SourceManifest, SourceSchema
from ..tasks import TaskStepId
from ..utils import download_http_files
from .duckdb_utils import convert_path_to_duckdb, duckdb_setup

LINE_NUMBER_COLUMN = '__line_number__'


class CSVSource(Source):
  """CSV data loader

  CSV files can live locally as a filepath, point to an external URL, or live on S3, GCS, or R2.

  For more details on authorizing access to S3, GCS or R2, see:
  https://duckdb.org/docs/guides/import/s3_import.html
  """  # noqa: D415, D400

  name: ClassVar[str] = 'csv'

  filepaths: list[str] = Field(
    description='A list of paths to CSV files. '
    'Paths can be local, point to an HTTP(s) url, or live on GCS, S3 or R2.'
  )
  delim: Optional[str] = Field(default=',', description='The CSV file delimiter to use.')
  header: Optional[bool] = Field(default=True, description='Whether the CSV file has a header row.')
  names: Optional[list[str]] = Field(
    default=None, description='Provide header names if the file does not contain a header.'
  )

  _source_schema: Optional[SourceSchema] = None
  _reader: Optional[pa.RecordBatchReader] = None
  _con: Optional[duckdb.DuckDBPyConnection] = None

  @override
  def setup(self) -> None:
    # Download CSV files to /tmp if they are via HTTP to speed up duckdb.
    filepaths = download_http_files(self.filepaths)

    self._con = duckdb.connect(database=':memory:')
    duckdb_setup(self._con)

    # DuckDB expects s3 protocol: https://duckdb.org/docs/guides/import/s3_import.html.
    duckdb_paths = [convert_path_to_duckdb(path) for path in filepaths]

    # NOTE: We use duckdb here to increase parallelism for multiple files.
    # NOTE: We turn off the parallel reader because of https://github.com/lilacai/lilac/issues/373.
    self._con.execute(
      f"""
      CREATE SEQUENCE serial START 1;
      CREATE VIEW t as (SELECT nextval('serial') as "{LINE_NUMBER_COLUMN}", * FROM read_csv_auto(
        {duckdb_paths},
        SAMPLE_SIZE=500000,
        HEADER={self.header},
        {f'NAMES={self.names},' if self.names else ''}
        DELIM='{self.delim or ','}',
        IGNORE_ERRORS=true,
        PARALLEL=false
    ));
    """
    )

    res = self._con.execute('SELECT COUNT(*) FROM t').fetchone()
    num_items = cast(tuple[int], res)[0]

    self._reader = self._con.execute('SELECT * from t').fetch_record_batch(rows_per_batch=10_000)
    # Create the source schema in prepare to share it between process and source_schema.
    schema = arrow_schema_to_schema(self._reader.schema)
    self._source_schema = SourceSchema(fields=schema.fields, num_items=num_items)

  @override
  def source_schema(self) -> SourceSchema:
    """Return the source schema."""
    assert self._source_schema is not None
    return self._source_schema

  @override
  def load_to_parquet(self, output_dir: str, task_step_id: Optional[TaskStepId]) -> SourceManifest:
    del task_step_id

    assert self._con, 'setup() must be called first.'

    out_filename = dataset_utils.get_parquet_filename(PARQUET_FILENAME_PREFIX, 0, 1)
    filepath = os.path.join(output_dir, out_filename)
    os.makedirs(output_dir, exist_ok=True)

    self._con.sql(
      f"SELECT replace(CAST(uuid() AS VARCHAR), ' - ', ' ') AS {ROWID}, * FROM t"
    ).write_parquet(filepath, compression='zstd')
    schema = Schema(fields=self.source_schema().fields.copy())
    return SourceManifest(files=[out_filename], data_schema=schema, source=self)
