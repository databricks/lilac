"""Load environment variables from .env file."""
import os
from typing import Any, Literal, Optional, Union, cast

from dotenv import load_dotenv

EnvironmentKeys = Union[Literal['LILAC_DATA_PATH'],
                        # Authentication on the demo.
                        Literal['LILAC_AUTH_ENABLED'], Literal['GOOGLE_CLIENT_ID'],
                        Literal['GOOGLE_CLIENT_SECRET'], Literal['LILAC_OAUTH_SECRET_KEY'],
                        # DuckDB accessing GCS.
                        Literal['GCS_REGION'], Literal['GCS_ACCESS_KEY'], Literal['GCS_SECRET_KEY'],
                        # Embedding API keys.
                        Literal['OPENAI_API_KEY'], Literal['COHERE_API_KEY'],
                        Literal['PALM_API_KEY'],
                        # HuggingFace demos.
                        Literal['HF_USERNAME'], Literal['HF_STAGING_DEMO_REPO'],
                        Literal['SPACE_ID'], Literal['HF_ACCESS_TOKEN'],
                        # DuckDB
                        Literal['DUCKDB_USE_VIEWS'],
                        # Debugging
                        Literal['DEBUG'], Literal['DISABLE_LOGS']]


def _init_env() -> None:
  in_test = os.environ.get('LILAC_TEST', None)
  # Load the .env files into the environment in order of highest to lowest priority.

  if not in_test:  # Skip local environment variables when testing.
    load_dotenv('.env.local')
  load_dotenv('.env.demo')
  load_dotenv('.env')

  if os.environ.get('LILAC_AUTH_ENABLED', None):
    if not os.environ.get('GOOGLE_CLIENT_ID', None) or not os.environ.get(
        'GOOGLE_CLIENT_SECRET', None):
      raise ValueError(
        'Missing `GOOGLE_CLIENT_ID` or `GOOGLE_CLIENT_SECRET` when `LILAC_AUTH_ENABLED=true`')
    SECRET_KEY = os.environ.get('LILAC_OAUTH_SECRET_KEY', None)
    if not SECRET_KEY:
      raise ValueError('Missing `LILAC_OAUTH_SECRET_KEY` when `LILAC_AUTH_ENABLED=true`')
  if os.environ.get('LILAC_AUTH_ENABLED', None):
    if not os.environ.get('GOOGLE_CLIENT_ID', None) or not os.environ.get(
        'GOOGLE_CLIENT_SECRET', None):
      raise ValueError(
        'Missing `GOOGLE_CLIENT_ID` or `GOOGLE_CLIENT_SECRET` when `LILAC_AUTH_ENABLED=true`')
    SECRET_KEY = os.environ.get('LILAC_OAUTH_SECRET_KEY', None)
    if not SECRET_KEY:
      raise ValueError('Missing `LILAC_OAUTH_SECRET_KEY` when `LILAC_AUTH_ENABLED=true`')


def env(key: EnvironmentKeys, default: Optional[Any] = None) -> Any:
  """Return the value of an environment variable."""
  return os.environ.get(key, default)


def data_path() -> str:
  """Return the base path for data."""
  return cast(str, env('LILAC_DATA_PATH', './data'))


# Initialize the environment at import time.
_init_env()
