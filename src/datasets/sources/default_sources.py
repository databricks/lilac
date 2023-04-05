"""Registers all available default sources."""
from .csv_source import CSVSource
from .huggingface_source import HuggingFaceDataset
from .pandas_source import PandasSource
from .source_registry import register_source
from .tfds_source import TensorFlowDataset


def register_default_sources() -> None:
  """Register all the default sources."""
  register_source(CSVSource)
  register_source(HuggingFaceDataset)
  register_source(PandasSource)
  register_source(TensorFlowDataset)
