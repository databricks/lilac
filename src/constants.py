"""Server constants."""
import os


def data_path() -> str:
  """Return the base path for data."""
  return os.environ['LILAC_DATA_PATH'] if 'LILAC_DATA_PATH' in os.environ else './gcs_cache'
