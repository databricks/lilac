"""Configurations for a dataset run."""
from typing import Optional

from pydantic import BaseModel, validator

from .data.dataset import DatasetSettings
from .schema import Path, PathTuple, normalize_path
from .signals.signal import Signal, TextEmbeddingSignal, get_signal_by_type, resolve_signal
from .sources.source import Source
from .sources.source_registry import resolve_source


class SignalConfig(BaseModel):
  """Configures a signal on a source path."""
  path: PathTuple
  signal: Signal

  @validator('path', pre=True)
  def parse_path(cls, path: Path) -> PathTuple:
    """Parse a path."""
    return normalize_path(path)

  @validator('signal', pre=True)
  def parse_signal(cls, signal: dict) -> Signal:
    """Parse a signal to its specific subclass instance."""
    return resolve_signal(signal)


class EmbeddingConfig(BaseModel):
  """Configures an embedding on a source path."""
  path: PathTuple
  embedding: str

  @validator('path', pre=True)
  def parse_path(cls, path: Path) -> PathTuple:
    """Parse a path."""
    return normalize_path(path)

  @validator('embedding', pre=True)
  def validate_embedding(cls, embedding: str) -> str:
    """Validate the embedding is registered."""
    get_signal_by_type(embedding, TextEmbeddingSignal)
    return embedding


class DatasetConfig(BaseModel):
  """Configures a dataset with a source and transformations."""
  # The namespace and name of the dataset.
  namespace: str
  name: str

  # The source configuration.
  source: Source

  # Model configuration: embeddings and signals on paths.
  embeddings: Optional[list[EmbeddingConfig]]
  # When defined, uses this list of signals instead of running all signals.
  signals: Optional[list[SignalConfig]]

  # Dataset settings, default embeddings and UI settings like media paths.
  settings: Optional[DatasetSettings]

  @validator('source', pre=True)
  def parse_source(cls, source: dict) -> Source:
    """Parse a source to its specific subclass instance."""
    return resolve_source(source)


class Config(BaseModel):
  """Configures a set of datasets for a lilac instance."""
  datasets: list[DatasetConfig]

  # When defined, uses this list of signals to run over every dataset, over all media paths, unless
  # signals is overridden by a specific dataset.
  signals: list[Signal] = []

  @validator('signals', pre=True)
  def parse_signal(cls, signals: list[dict]) -> list[Signal]:
    """Parse alist of signals to their specific subclass instances."""
    return [resolve_signal(signal) for signal in signals]
