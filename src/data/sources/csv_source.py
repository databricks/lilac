"""CSV source."""
import uuid
from typing import Iterable, Optional

import duckdb
import requests
from pydantic import Field
from typing_extensions import override

from ...config import CONFIG, data_path
from ...schema import UUID_COLUMN, Item
from ...utils import file_exists, log, open_file
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
    # Download CSV files to local cache if they are remote to speed up duckdb.
    gcs_filepaths: list[str] = []
    temp_files_to_delete = []
    for filepath in self.filepaths:
      if filepath.startswith(('http://', 'https://')):
        tmp_filename = uuid.uuid4().bytes.hex()
        gcs_filepath = f'{data_path()}/local_cache/{tmp_filename}'
        if not file_exists(gcs_filepath):
          log(f'Downloading CSV from url {filepath} to {gcs_filepath}')
          dl = requests.get(filepath, timeout=10000, allow_redirects=True)
          with open_file(gcs_filepath, 'wb') as f:
            f.write(dl.content)
          temp_files_to_delete.append(gcs_filepath)
        filepath = gcs_filepath
      else:
        if not file_exists(filepath):
          raise ValueError(f'CSV file {filepath} was not found.')
      gcs_filepaths.append(filepath)

    con = duckdb.connect(database=':memory:')
    con.install_extension('httpfs')
    con.load_extension('httpfs')

    # DuckDB expects s3 protocol: https://duckdb.org/docs/guides/import/s3_import.html.
    s3_filepaths = [path.replace('gs://', 's3://') for path in gcs_filepaths]

    delim = self.delim or ','
    csv_sql = f"""
      CREATE SEQUENCE serial START 1;
      SELECT nextval('serial')::STRING as {UUID_COLUMN}, *
      FROM read_csv_auto(
        {s3_filepaths},
        SAMPLE_SIZE=500000,
        DELIM='{delim}',
        IGNORE_ERRORS=true
    )
    """

    gcs_setup = ''
    if 'GCS_REGION' in CONFIG:
      gcs_setup = f"""
        SET s3_region='{CONFIG['GCS_REGION']}';
        SET s3_access_key_id='{CONFIG['GCS_ACCESS_KEY']}';
        SET s3_secret_access_key='{CONFIG['GCS_SECRET_KEY']}';
        SET s3_endpoint='storage.googleapis.com';
      """

    con.execute(f"""
      {gcs_setup}
      CREATE SEQUENCE serial START 1;
      CREATE VIEW csv_view AS ({csv_sql});
    """)
    df = con.execute('SELECT * FROM csv_view').fetchdf()

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
