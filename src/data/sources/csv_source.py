"""CSV source."""
import os
import time
import uuid
from typing import Optional

import duckdb
import pyarrow.parquet as pq
import requests
from pydantic import BaseModel, Field
from typing_extensions import override

from ...constants import data_path
from ...schema import PARQUET_FILENAME_PREFIX, ImageInfo, Path, arrow_schema_to_schema
from ...utils import (
    GCS_REGEX,
    UUID_COLUMN,
    CopyRequest,
    copy_files,
    delete_file,
    file_exists,
    get_image_path,
    log,
    makedirs,
    open_file,
)
from .source import ShardsLoader, Source, SourceProcessResult, SourceShardOut, default_shards_loader


class ImageColumn(BaseModel):
  """Info about the column that contains a link to the image file."""
  name: str
  subdir = ''
  path_suffix = ''


class ShardInfo(BaseModel):
  """Info about an individual csv file shard. Each shard is processed in parallel."""
  filepath: str
  shard_index: int
  num_shards: int
  output_dir: str
  delim: str
  image_columns: Optional[list[ImageColumn]]


class CSVDataset(Source):
  """CSV data loader

  CSV files can live locally as a filepath, or point to an external URL.
  """ # noqa: D415, D400
  name = 'csv'
  shard_info_cls = ShardInfo

  filepaths: list[str] = Field(description='A list of filepaths to CSV files.')
  delim: Optional[str] = Field(default=',', description='The CSV file delimiter to use.')
  image_columns: Optional[list[ImageColumn]] = Field(
      description=
      'A list of image columns specifying which columns associate with image information.')

  @override
  async def process(self,
                    output_dir: str,
                    shards_loader: Optional[ShardsLoader] = None) -> SourceProcessResult:
    """Process the source upload request."""
    shards_loader = shards_loader or default_shards_loader(self)

    start_time = time.time()
    gcs_filepaths: list[str] = []
    temp_files_to_delete = []
    for filepath in self.filepaths:
      if filepath.startswith(('http://', 'https://')):
        tmp_filename = uuid.uuid4().bytes.hex()
        gcs_filepath = f'{data_path()}/local_cache/{tmp_filename}'
        if not file_exists(gcs_filepath):
          log(f'Downloading CSV from url {filepath} to {gcs_filepath}')
          dl = requests.get(filepath, timeout=10000)
          with open_file(gcs_filepath, 'wb') as f:
            f.write(dl.content)
          temp_files_to_delete.append(gcs_filepath)
        filepath = gcs_filepath
      else:
        if not file_exists(filepath):
          raise ValueError(f'CSV file {filepath} was not found.')
      gcs_filepaths.append(filepath)

    elapsed = time.time() - start_time
    log(f'[CSV Source] Checking input CSV file existence took {elapsed:.2f} seconds.')
    num_shards = len(self.filepaths)
    delim = self.delim or ','
    shard_infos = [
        ShardInfo(filepath=path,
                  shard_index=i,
                  num_shards=num_shards,
                  output_dir=output_dir,
                  delim=delim,
                  image_columns=self.image_columns) for i, path in enumerate(gcs_filepaths)
    ]
    shard_outs = await shards_loader(shard_infos)

    filepaths = [shard_out.filepath for shard_out in shard_outs]
    num_items = sum(shard_out.num_items for shard_out in shard_outs)

    arrow_schema = pq.read_schema(open_file(filepaths[0], mode='rb'))
    schema = arrow_schema_to_schema(arrow_schema)
    images: Optional[list[ImageInfo]] = None
    if self.image_columns:
      images = [
          ImageInfo(path=_csv_column_to_path(image_column.name))
          for image_column in self.image_columns
      ]

    # Clean up the temporary files that we created for http CSV requests.
    for temp_filename in temp_files_to_delete:
      delete_file(temp_filename)
    return SourceProcessResult(filepaths=filepaths,
                               data_schema=schema,
                               images=images,
                               num_items=num_items)

  @override
  def process_shard(self, shard_info: ShardInfo) -> SourceShardOut:
    filepath = shard_info.filepath
    con = duckdb.connect(database=':memory:')
    con.install_extension('httpfs')
    con.load_extension('httpfs')
    delim = shard_info.delim
    # DuckDB expects s3 protocol: https://duckdb.org/docs/guides/import/s3_import.html.
    s3_filepath = filepath.replace('gs://', 's3://')
    # The sample size here is just used to infer the schema.
    # TODO(https://github.com/lilacml/lilac/issues/1): Remove this workaround when duckdb
    # supports direct casting uuid --> blob.
    blob_uuid = "regexp_replace(replace(uuid(), '-', ''), '.{2}', '\\\\x\\0', 'g')::BLOB"
    csv_sql = f"SELECT {blob_uuid} as {UUID_COLUMN}, * FROM read_csv_auto(\
      '{s3_filepath}', SAMPLE_SIZE=500000, DELIM='{delim}', IGNORE_ERRORS=true)"

    prefix = os.path.join(shard_info.output_dir, PARQUET_FILENAME_PREFIX)
    shard_index = shard_info.shard_index
    num_shards = shard_info.num_shards
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
      SET preserve_insertion_order=false;
      SET experimental_parallel_csv=true;
      COPY ({csv_sql}) TO '{s3_out_filepath}'
    """)

    shard_num_items = con.execute(f"""
      CREATE VIEW csv_view AS (SELECT * FROM read_parquet('{s3_out_filepath}'));
      SELECT COUNT({UUID_COLUMN}) FROM csv_view;
    """).fetchall()[0][0]

    # Copy the images from the source to the output dir.
    if shard_info.image_columns:
      image_col_names = ', '.join([column.name for column in shard_info.image_columns])
      result = con.execute(f"""
        SELECT {image_col_names}, {UUID_COLUMN} FROM csv_view;
      """).fetchall()

      copy_image_infos: list[CopyRequest] = []
      for row in result:
        row_id = row[-1]
        for i, image_column in enumerate(shard_info.image_columns):
          input_image_path = os.path.join(os.path.dirname(shard_info.filepath), image_column.subdir,
                                          f'{row[i]}{image_column.path_suffix}')
          copy_image_infos.append(
              CopyRequest(from_path=input_image_path,
                          to_path=get_image_path(output_dir=shard_info.output_dir,
                                                 path=_csv_column_to_path(image_column.name),
                                                 row_id=row_id)))

      log(f'[CSV Source] Copying {len(copy_image_infos)} images...')
      copy_files(copy_image_infos,
                 input_gcs=GCS_REGEX.match(shard_info.filepath) is not None,
                 output_gcs=GCS_REGEX.match(out_filepath) is not None)
    con.close()
    return SourceShardOut(filepath=out_filepath, num_items=int(shard_num_items))


def _csv_column_to_path(column_name: str) -> Path:
  return (column_name,)
