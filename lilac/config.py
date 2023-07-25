"""Load environment variables from .env file."""
import os
from typing import Any, Literal, Optional, Union, cast

from dotenv import dotenv_values

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
                        Literal['SPACE_ID'],
                        # DuckDB
                        Literal['DUCKDB_USE_VIEWS'],
                        # Debugging
                        Literal['DEBUG'], Literal['DISABLE_LOGS']]
_ENV: Optional[dict[str, Optional[str]]] = None


def env(key: EnvironmentKeys, default: Optional[Any] = None) -> Any:
  """Return the value of an environment variable."""
  global _ENV
  first_load = False
  # This is done lazily so we can prevent loading local environment variables when testing. The
  # 'PYTEST_CURRENT_TEST' environment variable is only set after module initialization by pytest.

  if _ENV is None:
    in_test = os.environ.get('LILAC_TEST', None)
    _ENV = {
      **dotenv_values('.env'),  # load shared variables
      **dotenv_values('.env.demo'),  # load demo-specific environment flags.
      **(dotenv_values('.env.local') if not in_test else {})
    }
    first_load = True

  # Override the file based configs with the current environment, in case flags have changed.
  environment = {**_ENV, **os.environ}

  if first_load:
    if environment.get('LILAC_AUTH_ENABLED', None):
      if not environment.get('GOOGLE_CLIENT_ID', None) or not environment.get(
          'GOOGLE_CLIENT_SECRET', None):
        raise ValueError(
          'Missing `GOOGLE_CLIENT_ID` or `GOOGLE_CLIENT_SECRET` when `LILAC_AUTH_ENABLED=true`')
      SECRET_KEY = environment.get('LILAC_OAUTH_SECRET_KEY', None)
      if not SECRET_KEY:
        raise ValueError('Missing `LILAC_OAUTH_SECRET_KEY` when `LILAC_AUTH_ENABLED=true`')

  return environment.get(key, default)


def data_path() -> str:
  """Return the base path for data."""
  return cast(str, env('LILAC_DATA_PATH', './data'))
