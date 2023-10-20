"""Utils for duckdb."""
import os

import duckdb

from ..env import env, get_project_dir


def duckdb_setup(con: duckdb.DuckDBPyConnection) -> None:
  """Setup DuckDB. This includes setting up the extensions directory and GCS access."""
  con.execute(f"""
    SET extension_directory='{os.path.join(get_project_dir(), '.duckdb')}';
  """)

  region = env('GCS_REGION') or env('S3_REGION')
  if region:
    con.execute(f"SET s3_region='{region}")

  access_key = env('GCS_ACCESS_KEY') or env('S3_ACCESS_KEY')
  if access_key:
    con.execute(f"SET s3_access_key_id='{access_key}")

  secret_key = env('GCS_SECRET_KEY') or env('S3_SECRET_KEY')
  if secret_key:
    con.execute(f"SET s3_secret_access_key='{secret_key}'")

  gcs_endpoint = 'storage.googleapis.com'
  endpoint = env('S3_ENDPOINT') or (gcs_endpoint if env('GCS_REGION') else None)
  if endpoint:
    con.execute(f"SET s3_endpoint='{endpoint}'")
