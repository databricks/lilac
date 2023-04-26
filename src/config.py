"""Load environment variables from .env file."""
import os

from dotenv import dotenv_values

config = {
    **dotenv_values('.env'),  # load shared variables
    **dotenv_values('.env.local'),  # load locally set variables
    **os.environ,  # override loaded values with environment variables
}


def data_path() -> str:
  """Return the base path for data."""
  if config['LILAC_DATA_PATH']:
    return config['LILAC_DATA_PATH']
  return './gcs_cache'
