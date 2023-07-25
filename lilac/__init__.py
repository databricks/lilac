from .data.dataset_duckdb import DatasetDuckDB
from .data.sources.csv_source import CSVDataset
from .data.sources.default_sources import register_default_sources
from .data.sources.gmail_source import Gmail
from .data.sources.huggingface_source import HuggingFaceDataset
from .data.sources.json_source import JSONDataset
from .data_loader import create_dataset
from .db_manager import get_dataset, set_default_dataset_cls
from .server import start_server, stop_server
from .signals.default_signals import register_default_signals

register_default_sources()
register_default_signals()
set_default_dataset_cls(DatasetDuckDB)

__all__ = [
  'start_server',
  'stop_server',
  'create_dataset',
  'get_dataset',

  # Source configurations.
  'HuggingFaceDataset',
  'CSVDataset',
  'JSONDataset',
  'Gmail',
]
