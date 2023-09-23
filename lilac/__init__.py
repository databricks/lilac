from importlib import metadata

from .concepts import *  # noqa: F403
from .config import Config, DatasetConfig, DatasetSettings, EmbeddingConfig, SignalConfig
from .data import *  # noqa: F403
from .data.dataset_duckdb import DatasetDuckDB
from .data_loader import create_dataset
from .db_manager import get_dataset, set_default_dataset_cls
from .embeddings import *  # noqa: F403
from .embeddings.default_vector_stores import register_default_vector_stores
from .env import *  # noqa: F403
from .env import LilacEnvironment, get_project_dir, set_project_dir
from .load import load
from .project import init
from .schema import *  # noqa: F403
from .schema import Field
from .server import start_server, stop_server
from .signals import *  # noqa: F403
from .signals.default_signals import register_default_signals
from .source import Source
from .sources import *  # noqa: F403
from .sources.default_sources import register_default_sources
from .splitters import *  # noqa: F403

try:
  __version__ = metadata.version('lilac')
except metadata.PackageNotFoundError:
  __version__ = ''

register_default_signals()
register_default_vector_stores()
set_default_dataset_cls(DatasetDuckDB)

# Avoids polluting the results of dir(__package__).
del (metadata, register_default_sources, register_default_signals, set_default_dataset_cls,
     DatasetDuckDB)

__all__ = [
  'start_server',
  'stop_server',
  'create_dataset',
  'get_dataset',
  'init',
  'load',
  'set_project_dir',
  'get_project_dir',
  'Config',
  'DatasetConfig',
  'EmbeddingConfig',
  'SignalConfig',
  'DatasetSettings',
  'LilacEnvironment',
  'Source',
  'Field',
]
