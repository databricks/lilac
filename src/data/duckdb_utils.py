"""Utils for duckdb."""
import duckdb

from ..config import CONFIG


def duckdb_gcs_setup(con: duckdb.DuckDBPyConnection) -> str:
  """Setup DuckDB for GCS."""
  con.install_extension('httpfs')
  con.load_extension('httpfs')

  if 'GCS_REGION' in CONFIG:
    return f"""
        SET s3_region='{CONFIG['GCS_REGION']}';
        SET s3_access_key_id='{CONFIG['GCS_ACCESS_KEY']}';
        SET s3_secret_access_key='{CONFIG['GCS_SECRET_KEY']}';
        SET s3_endpoint='storage.googleapis.com';
      """
  return ''
