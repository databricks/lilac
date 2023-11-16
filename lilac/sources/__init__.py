"""Sources for ingesting data into Lilac."""

from .csv_source import CSVSource
from .default_sources import register_default_sources
from .github_source import GithubSource
from .gmail_source import GmailSource
from .huggingface_source import HuggingFaceSource
from .json_source import JSONSource
from .langsmith import LangSmithSource
from .llama_index_docs_source import LlamaIndexDocsSource
from .pandas_source import PandasSource
from .parquet_source import ParquetSource

register_default_sources()

__all__ = [
  'HuggingFaceSource',
  'CSVSource',
  'JSONSource',
  'GmailSource',
  'PandasSource',
  'ParquetSource',
  'LangSmithSource',
  'GithubSource',
  'LlamaIndexDocsSource',
]
