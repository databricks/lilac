"""CSV source."""
import urllib.request
import uuid
from typing import Iterable

import duckdb
from pydantic import Field as PydanticField
from typing_extensions import override

from ...config import CONFIG, data_path
from ...schema import UUID_COLUMN, Item
from ...utils import file_exists, log
from .pandas_source import PandasDataset
from .source import Source, SourceSchema


class JSONDataset(Source):
  """JSON data loader

  Supports both JSON and JSONL. If using JSONL, set `json_format=newline_delimited`.

  JSON files can live locally as a filepath, or point to an external URL.
  """ # noqa: D415, D400
  name = 'json'

  filepaths: list[str] = PydanticField(description='A list of filepaths to JSON files.')

  _source_schema: SourceSchema
  _pd_source: PandasDataset

  @override
  def prepare(self) -> None:
    # Download JSON files to local cache if they are remote to speed up duckdb.
    gcs_filepaths: list[str] = []
    temp_files_to_delete = []
    for filepath in self.filepaths:
      if filepath.startswith(('http://', 'https://')):
        http_url = filepath
        tmp_filename = uuid.uuid4().bytes.hex()
        gcs_filepath = f'{data_path()}/local_cache/{tmp_filename}'
        if not file_exists(gcs_filepath):
          log(f'Downloading JSON from url {http_url} to {gcs_filepath}')

          urllib.request.urlretrieve(http_url, gcs_filepath)
          print('downloaded...')

          temp_files_to_delete.append(gcs_filepath)
        filepath = gcs_filepath
      else:
        if not file_exists(filepath):
          raise ValueError(f'JSON file {filepath} was not found.')
      gcs_filepaths.append(filepath)

    con = duckdb.connect(database=':memory:')
    con.install_extension('httpfs')
    con.load_extension('httpfs')

    # DuckDB expects s3 protocol: https://duckdb.org/docs/guides/import/s3_import.html.
    s3_filepaths = [path.replace('gs://', 's3://') for path in gcs_filepaths]

    json_sql = f"""
      CREATE SEQUENCE serial START 1;
      SELECT nextval('serial')::STRING as {UUID_COLUMN}, *
      FROM read_json_auto(
        {s3_filepaths},
        IGNORE_ERRORS=true
      )"""

    gcs_setup = ''
    if 'GCS_REGION' in CONFIG:
      gcs_setup = f"""
        SET s3_region='{CONFIG['GCS_REGION']}';
        SET s3_access_key_id='{CONFIG['GCS_ACCESS_KEY']}';
        SET s3_secret_access_key='{CONFIG['GCS_SECRET_KEY']}';
        SET s3_endpoint='storage.googleapis.com';
      """

    df = con.execute(f"""
      {gcs_setup}
      {json_sql}
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
