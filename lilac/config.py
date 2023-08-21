"""Configurations for a dataset run."""

import json
import pathlib
from typing import TYPE_CHECKING, Any, Optional, Union

import yaml

if TYPE_CHECKING:
  from pydantic.typing import AbstractSetIntStr, MappingIntStrAny

from pydantic import BaseModel, Extra, ValidationError, validator

from .schema import Path, PathTuple, normalize_path
from .signal import Signal, TextEmbeddingSignal, get_signal_by_type, resolve_signal
from .sources.source import Source
from .sources.source_registry import resolve_source

CONFIG_FILENAME = 'config.yml'


def _serializable_path(path: PathTuple) -> Union[str, list]:
  if len(path) == 1:
    return path[0]
  return list(path)


class SignalConfig(BaseModel):
  """Configures a signal on a source path."""
  path: PathTuple
  signal: Signal

  class Config:
    extra = Extra.forbid

  @validator('path', pre=True)
  def parse_path(cls, path: Path) -> PathTuple:
    """Parse a path."""
    return normalize_path(path)

  @validator('signal', pre=True)
  def parse_signal(cls, signal: dict) -> Signal:
    """Parse a signal to its specific subclass instance."""
    return resolve_signal(signal)

  def dict(
    self,
    *,
    include: Optional[Union['AbstractSetIntStr', 'MappingIntStrAny']] = None,
    exclude: Optional[Union['AbstractSetIntStr', 'MappingIntStrAny']] = None,
    by_alias: bool = False,
    skip_defaults: Optional[bool] = None,
    exclude_unset: bool = False,
    exclude_defaults: bool = False,
    exclude_none: bool = False,
  ) -> dict[str, Any]:
    """Override the default dict method to simplify the path tuples.

    This is required to remove the python-specific tuple dump in the yaml file.
    """
    res = super().dict(
      include=include,
      exclude=exclude,
      by_alias=by_alias,
      skip_defaults=skip_defaults,
      exclude_unset=exclude_unset,
      exclude_defaults=exclude_defaults,
      exclude_none=exclude_none)
    res['path'] = _serializable_path(res['path'])
    return res


class EmbeddingConfig(BaseModel):
  """Configures an embedding on a source path."""
  path: PathTuple
  embedding: str

  class Config:
    extra = Extra.forbid

  def dict(
    self,
    *,
    include: Optional[Union['AbstractSetIntStr', 'MappingIntStrAny']] = None,
    exclude: Optional[Union['AbstractSetIntStr', 'MappingIntStrAny']] = None,
    by_alias: bool = False,
    skip_defaults: Optional[bool] = None,
    exclude_unset: bool = False,
    exclude_defaults: bool = False,
    exclude_none: bool = False,
  ) -> dict[str, Any]:
    """Override the default dict method to simplify the path tuples.

    This is required to remove the python-specific tuple dump in the yaml file.
    """
    res = super().dict(
      include=include,
      exclude=exclude,
      by_alias=by_alias,
      skip_defaults=skip_defaults,
      exclude_unset=exclude_unset,
      exclude_defaults=exclude_defaults,
      exclude_none=exclude_none)
    res['path'] = _serializable_path(res['path'])
    return res

  @validator('path', pre=True)
  def parse_path(cls, path: Path) -> PathTuple:
    """Parse a path."""
    return normalize_path(path)

  @validator('embedding', pre=True)
  def validate_embedding(cls, embedding: str) -> str:
    """Validate the embedding is registered."""
    get_signal_by_type(embedding, TextEmbeddingSignal)
    return embedding


class DatasetUISettings(BaseModel):
  """The UI persistent settings for a dataset."""
  media_paths: list[PathTuple] = []
  markdown_paths: list[PathTuple] = []

  class Config:
    extra = Extra.forbid

  @validator('media_paths', pre=True)
  def parse_media_paths(cls, media_paths: list) -> list:
    """Parse a path, ensuring it is a tuple."""
    return [normalize_path(path) for path in media_paths]

  def dict(
    self,
    *,
    include: Optional[Union['AbstractSetIntStr', 'MappingIntStrAny']] = None,
    exclude: Optional[Union['AbstractSetIntStr', 'MappingIntStrAny']] = None,
    by_alias: bool = False,
    skip_defaults: Optional[bool] = None,
    exclude_unset: bool = False,
    exclude_defaults: bool = False,
    exclude_none: bool = False,
  ) -> dict[str, Any]:
    """Override the default dict method to simplify the path tuples.

    This is required to remove the python-specific tuple dump in the yaml file.
    """
    # TODO(nsthorat): Migrate this to @field_serializer when we upgrade to pydantic v2.
    res = super().dict(
      include=include,
      exclude=exclude,
      by_alias=by_alias,
      skip_defaults=skip_defaults,
      exclude_unset=exclude_unset,
      exclude_defaults=exclude_defaults,
      exclude_none=exclude_none)
    if 'media_paths' in res:
      res['media_paths'] = [_serializable_path(path) for path in res['media_paths']]
    if 'markdown_paths' in res:
      res['markdown_paths'] = [_serializable_path(path) for path in res['markdown_paths']]
    return res


class DatasetSettings(BaseModel):
  """The persistent settings for a dataset."""
  ui: Optional[DatasetUISettings] = None
  preferred_embedding: Optional[str] = None

  class Config:
    extra = Extra.forbid


class DatasetConfig(BaseModel):
  """Configures a dataset with a source and transformations."""
  # The namespace and name of the dataset.
  namespace: str
  name: str
  # Tags to organize datasets.
  tags: list[str] = []

  # The source configuration.
  source: Source

  # Model configuration: embeddings and signals on paths.
  embeddings: list[EmbeddingConfig] = []
  # When defined, uses this list of signals instead of running all signals.
  signals: list[SignalConfig] = []

  # Dataset settings, default embeddings and UI settings like media paths.
  settings: Optional[DatasetSettings] = None

  class Config:
    extra = Extra.forbid

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

  # A list of embeddings to compute the model caches for, for all concepts.
  concept_model_cache_embeddings: list[str] = []

  class Config:
    extra = Extra.forbid

  @validator('signals', pre=True)
  def parse_signal(cls, signals: list[dict]) -> list[Signal]:
    """Parse alist of signals to their specific subclass instances."""
    return [resolve_signal(signal) for signal in signals]


def read_config(config_path: str) -> Config:
  """Reads a config file.

  The config file can either be a `Config` or a `DatasetConfig`.

  The result is always a `Config` object. If the input is a `DatasetConfig`, the config will just
  contain a single dataset.
  """
  config_ext = pathlib.Path(config_path).suffix
  if config_ext in ['.yml', '.yaml']:
    with open(config_path, 'r') as f:
      config_dict = yaml.safe_load(f)
  elif config_ext in ['.json']:
    with open(config_path, 'r') as f:
      config_dict = json.load(f)
  else:
    raise ValueError(f'Unsupported config file extension: {config_ext}')

  config: Optional[Config] = None
  is_config = True
  try:
    config = Config(**config_dict)
  except ValidationError:
    is_config = False

  if not is_config:
    try:
      dataset_config = DatasetConfig(**config_dict)
      config = Config(datasets=[dataset_config])
    except ValidationError as error:
      raise ValidationError(
        'Config is not a valid `Config` or `DatasetConfig`', model=DatasetConfig) from error
  assert config is not None

  return config
