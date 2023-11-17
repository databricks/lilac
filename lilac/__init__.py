from importlib import metadata

from .concepts import *  # noqa: F403
from .config import (
  Config,
  DatasetConfig,
  DatasetSettings,
  DatasetUISettings,
  EmbeddingConfig,
  SignalConfig,
)
from .data import *  # noqa: F403
from .data.dataset_duckdb import DatasetDuckDB
from .db_manager import get_dataset, set_default_dataset_cls
from .deploy import deploy_config, deploy_project
from .embeddings import *  # noqa: F403
from .env import *  # noqa: F403
from .env import LilacEnvironment, get_project_dir, set_project_dir
from .load import load
from .load_dataset import create_dataset
from .project import init
from .schema import *  # noqa: F403
from .schema import Field
from .server import start_server, stop_server
from .signals import *  # noqa: F403
from .source import Source
from .sources import *  # noqa: F403
from .splitters import *  # noqa: F403

try:
  __version__ = metadata.version('lilac')
except metadata.PackageNotFoundError:
  __version__ = ''

set_default_dataset_cls(DatasetDuckDB)

# Avoids polluting the results of dir(__package__).
del (
  metadata,
  set_default_dataset_cls,
  DatasetDuckDB,
)

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
  'DatasetUISettings',
  'LilacEnvironment',
  'Source',
  'Field',
  'deploy_project',
  'deploy_config',
]
