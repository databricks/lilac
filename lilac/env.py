"""Load environment variables from .env file."""
import os
from typing import Any, Optional, cast

from dotenv import load_dotenv
from pydantic import BaseModel
from pydantic import Field as PydanticField


# NOTE: This is created for documentation, but isn't parsed by pydantic until we update to 2.0.
class LilacEnvironment(BaseModel):
  """Lilac environment variables.

  These can be set with operating system environment variables to override behavior.

  For python, see: https://docs.python.org/3/library/os.html#os.environ

  For bash, see: https://www.gnu.org/software/bash/manual/bash.html#Environment
  """
  # General Lilac environment variables.
  LILAC_DATA_PATH: str = PydanticField(
    description='The Lilac data path where datasets, concepts, caches are stored.',)
  DEBUG: str = PydanticField(
    description='Turn on Lilac debug mode to log queries and timing information.')
  DISABLE_LOGS: str = PydanticField(description='Disable log() statements to the console.')

  # API Keys.
  OPENAI_API_KEY: str = PydanticField(
    description='The OpenAI API key, used for computing `openai` embeddings and generating '
    'positive examples for concept seeding.')
  COHERE_API_KEY: str = PydanticField(
    description='The Cohere API key, used for computing `cohere` embeddings.')
  PALM_API_KEY: str = PydanticField(
    description='The PaLM API key, used for computing `palm` embeddings.')

  # HuggingFace demo.
  HF_ACCESS_TOKEN: str = PydanticField(
    description='The HuggingFace access token, used for downloading data to a space from a '
    'private dataset. This is also required if the HuggingFace space is private.')

  # DuckDB.
  DUCKDB_USE_VIEWS: str = PydanticField(
    description='Whether DuckDB uses views (1), or DuckDB tables (0). Views allow for much less '
    'RAM consumption, with a runtime query penalty. When using DuckDB tables (0), demos will '
    'take more RAM but be much faster during query time.')

  # Authentication.
  LILAC_AUTH_ENABLED: str = PydanticField(
    description='Set to true to enable read-only mode, disabling the ability to add datasets & '
    'compute dataset signals. When enabled, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` and '
    '`LILAC_OAUTH_SECRET_KEY` should also be set.')
  GOOGLE_CLIENT_ID: str = PydanticField(
    description=
    'The Google OAuth client ID. Required when `LILAC_AUTH_ENABLED=true`. Details can be found at '
    'https://developers.google.com/identity/protocols/oauth2.')
  GOOGLE_CLIENT_SECRET: str = PydanticField(
    description='The Google OAuth client secret. Details can be found at '
    'https://developers.google.com/identity/protocols/oauth2.')
  LILAC_OAUTH_SECRET_KEY: str = PydanticField(
    description='The Google OAuth random secret key. Details can be found at '
    'https://developers.google.com/identity/protocols/oauth2.')


def _init_env() -> None:
  in_test = os.environ.get('LILAC_TEST', None)
  # Load the .env files into the environment in order of highest to lowest priority.

  if not in_test:  # Skip local environment variables when testing.
    load_dotenv('.env.local')
  load_dotenv('.env.demo')
  load_dotenv('.env')

  auth_enabled = os.environ.get('LILAC_AUTH_ENABLED', False) == 'true'
  if auth_enabled:
    if not os.environ.get('GOOGLE_CLIENT_ID', None) or not os.environ.get(
        'GOOGLE_CLIENT_SECRET', None):
      raise ValueError(
        'Missing `GOOGLE_CLIENT_ID` or `GOOGLE_CLIENT_SECRET` when `LILAC_AUTH_ENABLED=true`')
    SECRET_KEY = os.environ.get('LILAC_OAUTH_SECRET_KEY', None)
    if not SECRET_KEY:
      raise ValueError('Missing `LILAC_OAUTH_SECRET_KEY` when `LILAC_AUTH_ENABLED=true`')
  if auth_enabled:
    if not os.environ.get('GOOGLE_CLIENT_ID', None) or not os.environ.get(
        'GOOGLE_CLIENT_SECRET', None):
      raise ValueError(
        'Missing `GOOGLE_CLIENT_ID` or `GOOGLE_CLIENT_SECRET` when `LILAC_AUTH_ENABLED=true`')
    SECRET_KEY = os.environ.get('LILAC_OAUTH_SECRET_KEY', None)
    if not SECRET_KEY:
      raise ValueError('Missing `LILAC_OAUTH_SECRET_KEY` when `LILAC_AUTH_ENABLED=true`')


def env(key: str, default: Optional[Any] = None) -> Any:
  """Return the value of an environment variable."""
  return os.environ.get(key, default)


def data_path() -> str:
  """Return the base path for data."""
  return cast(str, env('LILAC_DATA_PATH', './data'))


# Initialize the environment at import time.
_init_env()
