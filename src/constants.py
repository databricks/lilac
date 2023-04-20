"""Pydantic models for data, stored on GCS."""
import os

DATA_JSON_FILENAME = 'data.json'
EMBEDDINGS_FILENAME = 'embeddings.npy'


def data_path() -> str:
  """Return the base path for data."""
  return os.environ['LILAC_DATA_PATH'] if 'LILAC_DATA_PATH' in os.environ else './gcs_cache'
