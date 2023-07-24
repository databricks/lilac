"""Load environment variables from .env file."""
import os
from typing import Optional, cast

from dotenv import dotenv_values

CONFIG: dict[str, Optional[str]] = {
  **dotenv_values('.env'),  # load shared variables
  **dotenv_values('.env.local'),  # load locally set variables
  **dotenv_values('.env.demo'),  # load demo-specific environment flags.
  **os.environ,  # override loaded values with environment variables
}


def data_path() -> str:
  """Return the base path for data."""
  return cast(str, CONFIG.get('LILAC_DATA_PATH', './data'))
