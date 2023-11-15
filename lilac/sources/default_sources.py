"""Registers all available default sources."""
from ..source import register_source
from .csv_source import CSVSource
from .github_source import GithubSource
from .gmail_source import GmailSource
from .huggingface_source import HuggingFaceSource
from .json_source import JSONSource
from .langsmith import LangSmithSource
from .llama_index_docs_source import LlamaIndexDocsSource
from .pandas_source import PandasSource
from .parquet_source import ParquetSource
from .sqlite_source import SQLiteSource


def register_default_sources() -> None:
  """Register all the default sources."""
  register_source(CSVSource)
  register_source(HuggingFaceSource)
  register_source(JSONSource)
  register_source(PandasSource)
  register_source(GmailSource)
  register_source(ParquetSource)
  register_source(LangSmithSource)
  register_source(SQLiteSource)
  register_source(GithubSource)
  register_source(LlamaIndexDocsSource)
