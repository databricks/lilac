"""Registers all available default sources."""
from .csv_source import CSVDataset
from .huggingface_source import HuggingFaceDataset
from .json_source import JSONDataset
from .pandas_source import PandasDataset
from .reddit_hf_source import RedditDataset
from .source_registry import register_source


def register_default_sources() -> None:
  """Register all the default sources."""
  register_source(CSVDataset)
  register_source(HuggingFaceDataset)
  register_source(RedditDataset)
  register_source(JSONDataset)
  register_source(PandasDataset)
