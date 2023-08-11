from importlib import metadata

from .data import *  # noqa: F403
from .data.dataset_duckdb import DatasetDuckDB
from .data_loader import create_dataset
from .db_manager import get_dataset, set_default_dataset_cls
from .embeddings.default_vector_stores import register_default_vector_stores
from .server import start_server, stop_server
from .signals import *  # noqa: F403
from .signals.default_signals import register_default_signals
from .sources import *  # noqa: F403
from .sources.default_sources import register_default_sources

try:
  __version__ = metadata.version('lilacai')
except metadata.PackageNotFoundError:
  __version__ = ''

register_default_sources()
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
]
