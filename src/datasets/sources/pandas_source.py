"""Pandas source."""
import os
import time
from typing import Any, Optional

import duckdb
import pandas as pd
import pyarrow.parquet as pq
from pydantic import BaseModel
from typing_extensions import override

from ...schema import PARQUET_FILENAME_PREFIX, ImageInfo, Path, arrow_schema_to_schema
from ...utils import (
    GCS_REGEX,
    UUID_COLUMN,
    CopyRequest,
    copy_files,
    get_image_path,
    log,
    makedirs,
    open_file,
)
from .source import ShardsLoader, Source, SourceProcessResult


class ImageColumn(BaseModel):
  """Info about the column that contains a link to the image file."""
  name: str
  subdir = ''
  path_suffix = ''


class ShardInfo(BaseModel):
  """Info about an individual file shard. Each shard is processed in parallel."""
  output_dir: str
  image_base_path: Optional[str]
  image_columns: Optional[list[ImageColumn]]


class ShardOut(BaseModel):
  """Output of processing a single shard."""
  filepath: str
  num_items: int


class PandasSource(Source):
  """Pandas source."""
  name = 'pandas'

  _df: pd.DataFrame

  # The base path of the images files. We prepend this to the image path column in the dataframe.
  image_base_path: Optional[str]
  image_columns: Optional[list[ImageColumn]]

  class Config:
    underscore_attrs_are_private = True

  def __init__(self, df: pd.DataFrame, **kwargs: Any):
    super().__init__(**kwargs)
    self._df = df

  async def process(self, output_dir: str, shards_loader: ShardsLoader) -> SourceProcessResult:
    """Process the source upload request."""
    shard_info = ShardInfo(image_base_path=self.image_base_path,
                           output_dir=output_dir,
                           image_columns=self.image_columns).dict(exclude_none=True)

    start_time = time.time()
    shard_outs = [ShardOut(**x) for x in (await shards_loader([shard_info]))]
    elapsed = time.time() - start_time
    log(f'[Pandas Source] Converting pandas to parquet took {elapsed:.2f} seconds.')

    filepaths: list[str] = [x.filepath for x in shard_outs]
    num_items = sum(x.num_items for x in shard_outs)
    arrow_schema = pq.read_schema(open_file(filepaths[0], mode='rb'))
    schema = arrow_schema_to_schema(arrow_schema)
    images: Optional[list[ImageInfo]] = None
    if self.image_columns:
      images = [
          ImageInfo(path=_pandas_column_to_path(image_column.name))
          for image_column in self.image_columns
      ]

    return SourceProcessResult(filepaths=filepaths,
                               data_schema=schema,
                               images=images,
                               num_items=num_items)

  @override
  def process_shard(self, shard_info_dict: dict) -> dict:
    shard_info = ShardInfo(**shard_info_dict)
    con = duckdb.connect(database=':memory:')
    con.install_extension('httpfs')
    con.load_extension('httpfs')

    # Register the dataframe as a duckdb view.
    con.register('df', self._df)

    # TODO(https://github.com/lilacml/lilac/issues/1): Remove this workaround when duckdb
    # supports direct casting uuid --> blob.
    blob_uuid = "regexp_replace(replace(uuid(), '-', ''), '.{2}', '\\\\x\\0', 'g')::BLOB"
    pd_sql = f'SELECT {blob_uuid} as {UUID_COLUMN}, * FROM df'

    prefix = os.path.join(shard_info.output_dir, PARQUET_FILENAME_PREFIX)
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
      SET preserve_insertion_order=false;
      COPY ({pd_sql}) TO '{s3_out_filepath}'
    """)

    shard_num_items = con.execute(f"""
      CREATE VIEW pd_view AS (SELECT * FROM read_parquet('{s3_out_filepath}'));
      SELECT COUNT({UUID_COLUMN}) FROM pd_view;
    """).fetchall()[0][0]

    # Copy the images from the source to the output dir.
    if shard_info.image_columns:
      if not shard_info.image_base_path:
        raise ValueError('image_base_path must be set if image_columns is set.')

      image_base_path = shard_info.image_base_path
      image_col_names = ', '.join([column.name for column in shard_info.image_columns])
      result = con.execute(f"""
        SELECT {image_col_names}, {UUID_COLUMN} FROM pd_view;
      """).fetchall()

      copy_image_infos: list[CopyRequest] = []
      for row in result:
        row_id = row[-1]
        for i, image_column in enumerate(shard_info.image_columns):
          input_image_path = os.path.join(os.path.dirname(image_base_path), image_column.subdir,
                                          f'{row[i]}{image_column.path_suffix}')
          copy_image_infos.append(
              CopyRequest(from_path=input_image_path,
                          to_path=get_image_path(output_dir=shard_info.output_dir,
                                                 path=_pandas_column_to_path(image_column.name),
                                                 row_id=row_id)))

      log(f'[Pandas Source] Copying {len(copy_image_infos)} images...')
      copy_files(copy_image_infos,
                 input_gcs=GCS_REGEX.match(image_base_path) is not None,
                 output_gcs=GCS_REGEX.match(out_filepath) is not None)
    con.close()
    return {'filepath': out_filepath, 'num_items': int(shard_num_items)}


def _pandas_column_to_path(column_name: str) -> Path:
  return (column_name,)
