"""CSV source."""
import os
import uuid
from enum import Enum
from typing import Optional

import duckdb
import pyarrow.parquet as pq
import requests
from pydantic import Field
from typing_extensions import override

from ...constants import data_path
from ...schema import PARQUET_FILENAME_PREFIX, arrow_schema_to_schema
from ...tasks import TaskId
from ...utils import (
    UUID_COLUMN,
    delete_file,
    file_exists,
    log,
    makedirs,
    open_file,
)
from .source import Source, SourceProcessResult


class JSONFormat(str, Enum):
  """JSON format options."""
  AUTO = 'auto'
  RECORDS = 'records'
  ARRAY_OF_RECORDS = 'array_of_records'
  VALUES = 'values'
  ARRAY_OF_VALUES = 'array_of_values'


class JSONDataset(Source):
  """JSON data loader

  Supports both JSON and JSONL. If using JSONL, set `json_format=records`.

  JSON files can live locally as a filepath, or point to an external URL.
  """ # noqa: D415, D400
  name = 'json'

  filepaths: list[str] = Field(description='A list of filepaths to JSON files.')
  json_format: JSONFormat = Field(
      default=JSONFormat.AUTO,
      description=
      "Can be one of ['auto', 'records', 'array_of_records', 'values', 'array_of_values'].")

  @override
  def process(self, output_dir: str, task_id: Optional[TaskId] = None) -> SourceProcessResult:
    """Process the source upload request."""
    # Download JSON files to local cache if they are remote to speed up duckdb.
    gcs_filepaths: list[str] = []
    temp_files_to_delete = []
    for filepath in self.filepaths:
      if filepath.startswith(('http://', 'https://')):
        tmp_filename = uuid.uuid4().bytes.hex()
        gcs_filepath = f'{data_path()}/local_cache/{tmp_filename}'
        if not file_exists(gcs_filepath):
          log(f'Downloading JSON from url {filepath} to {gcs_filepath}')
          dl = requests.get(filepath, timeout=10000, allow_redirects=True)
          with open_file(gcs_filepath, 'wb') as f:
            f.write(dl.content)
          temp_files_to_delete.append(gcs_filepath)
        filepath = gcs_filepath
      else:
        if not file_exists(filepath):
          raise ValueError(f'JSON file {filepath} was not found.')
      gcs_filepaths.append(filepath)

    con = duckdb.connect(database=':memory:')
    con.install_extension('httpfs')
    con.load_extension('httpfs')
    con.install_extension('json')
    con.load_extension('json')
    # DuckDB expects s3 protocol: https://duckdb.org/docs/guides/import/s3_import.html.
    s3_filepaths = [path.replace('gs://', 's3://') for path in gcs_filepaths]
    # The sample size here is just used to infer the schema.
    # TODO(https://github.com/lilacml/lilac/issues/1): Remove this workaround when duckdb
    # supports direct casting uuid --> blob.
    blob_uuid = "regexp_replace(replace(uuid(), '-', ''), '.{2}', '\\\\x\\0', 'g')::BLOB"
    json_sql = f'SELECT {blob_uuid} as {UUID_COLUMN}, * FROM read_json(\
      {s3_filepaths}, json_format="{self.json_format}", IGNORE_ERRORS=true, AUTO_DETECT=true)'

    prefix = os.path.join(output_dir, PARQUET_FILENAME_PREFIX)
    shard_index = 0
    num_shards = 1
    out_filepath = f'{prefix}-{shard_index:05d}-of-{num_shards:05d}.parquet'

    # DuckDB won't create the parent dirs so we have to create it.
    out_dirname = os.path.dirname(out_filepath)
    makedirs(out_dirname)
    gcs_setup = ''
    if 'GCS_REGION' in os.environ:
      gcs_setup = f"""
        SET s3_region='{os.environ['GCS_REGION']}';
        SET s3_access_key_id='{os.environ['GCS_ACCESS_KEY']}';
        SET s3_secret_access_key='{os.environ['GCS_SECRET_KEY']}';
        SET s3_endpoint='storage.googleapis.com';
      """
    # DuckDB expects s3 protocol: https://duckdb.org/docs/guides/import/s3_import.html.
    s3_out_filepath = out_filepath.replace('gs://', 's3://')
    con.execute(f"""
      {gcs_setup}
      COPY ({json_sql}) TO '{s3_out_filepath}'
    """)

    num_items = con.execute(f"""
      CREATE VIEW json_view AS (SELECT * FROM read_parquet('{s3_out_filepath}'));
      SELECT COUNT({UUID_COLUMN}) FROM json_view;
    """).fetchall()[0][0]

    con.close()

    filepaths = [s3_out_filepath]

    arrow_schema = pq.read_schema(open_file(filepaths[0], mode='rb'))
    schema = arrow_schema_to_schema(arrow_schema)
    # Clean up the temporary files that we created for http JSON requests.
    for temp_filename in temp_files_to_delete:
      delete_file(temp_filename)

    return SourceProcessResult(filepaths=filepaths, data_schema=schema, num_items=num_items)
