"""Utils for duckdb."""
import os

import duckdb

from ..config import CONFIG, data_path


def duckdb_setup(con: duckdb.DuckDBPyConnection) -> str:
  """Setup DuckDB. This includes setting up the extensions directory and GCS access."""
  con.execute(f"""
    SET extension_directory='{os.path.join(data_path(), '.duckdb')}';
  """)

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
