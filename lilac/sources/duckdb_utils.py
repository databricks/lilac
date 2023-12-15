"""Utils for duckdb."""

import urllib.parse

import duckdb

from ..env import env


def duckdb_setup(con: duckdb.DuckDBPyConnection) -> None:
  """Setup DuckDB. This includes setting up performance optimizations."""
  con.execute(
    """
    SET enable_http_metadata_cache=true;
    SET enable_object_cache=true;
  """
  )


def convert_path_to_duckdb(filepath: str) -> str:
  """Convert a filepath to a duckdb filepath."""
  scheme = urllib.parse.urlparse(filepath).scheme
  options: dict[str, str] = {}
  if scheme == '':
    return filepath
  elif scheme == 'gs':
    options['s3_endpoint'] = 'storage.googleapis.com'
    if env('GCS_REGION'):
      options['s3_region'] = env('GCS_REGION')
    if env('GCS_ACCESS_KEY'):
      options['s3_access_key_id'] = env('GCS_ACCESS_KEY')
    if env('GCS_SECRET_KEY'):
      options['s3_secret_access_key'] = env('GCS_SECRET_KEY')
    filepath = filepath.replace('gs://', 's3://')
  elif scheme == 's3':
    if env('S3_ENDPOINT'):
      options['s3_endpoint'] = env('S3_ENDPOINT')
    if env('S3_REGION'):
      options['s3_region'] = env('S3_REGION')
    if env('S3_ACCESS_KEY'):
      options['s3_access_key_id'] = env('S3_ACCESS_KEY')
    if env('S3_SECRET_KEY'):
      options['s3_secret_access_key'] = env('S3_SECRET_KEY')
  else:
    raise ValueError(f'Unsupported scheme: {scheme}')
  if options:
    return f'{filepath}?{urllib.parse.urlencode(options, safe="+/")}'
  return filepath
