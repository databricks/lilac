"""Utils for duckdb."""

import duckdb

from ..env import env


def duckdb_setup(con: duckdb.DuckDBPyConnection) -> None:
  """Setup DuckDB. This includes setting up the extensions directory and GCS access."""
  region = env('GCS_REGION') or env('S3_REGION')
  if region:
    con.execute(f"SET s3_region='{region}'")

  access_key = env('GCS_ACCESS_KEY') or env('S3_ACCESS_KEY')
  if access_key:
    con.execute(f"SET s3_access_key_id='{access_key}'")

  secret_key = env('GCS_SECRET_KEY') or env('S3_SECRET_KEY')
  if secret_key:
    con.execute(f"SET s3_secret_access_key='{secret_key}'")

  gcs_endpoint = 'storage.googleapis.com'
  endpoint = env('S3_ENDPOINT') or (gcs_endpoint if env('GCS_REGION') else None)
  if endpoint:
    con.execute(f"SET s3_endpoint='{endpoint}'")

  con.execute("""
    SET enable_http_metadata_cache=true;
    SET enable_object_cache=true;
  """)
