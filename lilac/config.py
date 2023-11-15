"""Configurations for a dataset run."""

import json
import pathlib
from typing import Literal, Optional, Union

import yaml
from pydantic import (
  BaseModel,
  ConfigDict,
  SerializeAsAny,
  ValidationError,
  field_serializer,
  field_validator,
)
from pydantic import Field as PydanticField

from .embeddings.embedding import EMBEDDING_SORT_PRIORITIES
from .schema import Path, PathTuple, normalize_path
from .signal import Signal, TextEmbeddingSignal, get_signal_by_type, resolve_signal
from .source import Source, resolve_source

DEFAULT_EMBEDDING = EMBEDDING_SORT_PRIORITIES[0]

OLD_CONFIG_FILENAME = 'config.yml'


def _serializable_path(path: PathTuple) -> Union[str, list]:
  if len(path) == 1:
    return path[0]
  return list(path)


class SignalConfig(BaseModel):
  """Configures a signal on a source path."""

  path: PathTuple
  signal: SerializeAsAny[Signal]
  model_config = ConfigDict(extra='forbid')

  @field_validator('path', mode='before')
  @classmethod
  def parse_path(cls, path: Path) -> PathTuple:
    """Parse a path."""
    return normalize_path(path)

  @field_serializer('path')
  def serialize_path(self, path: PathTuple) -> Union[str, list[str]]:
    """Serialize a path."""
    return _serializable_path(path)

  @field_validator('signal', mode='before')
  @classmethod
  def parse_signal(cls, signal: dict) -> Signal:
    """Parse a signal to its specific subclass instance."""
    return resolve_signal(signal)


class EmbeddingConfig(BaseModel):
  """Configures an embedding on a source path."""

  path: PathTuple
  embedding: str
  model_config = ConfigDict(extra='forbid')

  @field_validator('path', mode='before')
  @classmethod
  def parse_path(cls, path: Path) -> PathTuple:
    """Parse a path."""
    return normalize_path(path)

  @field_serializer('path')
  def serialize_path(self, path: PathTuple) -> Union[str, list[str]]:
    """Serialize a path."""
    return _serializable_path(path)

  @field_validator('embedding', mode='before')
  @classmethod
  def validate_embedding(cls, embedding: str) -> str:
    """Validate the embedding is registered."""
    get_signal_by_type(embedding, TextEmbeddingSignal)
    return embedding


class DatasetUISettings(BaseModel):
  """The UI persistent settings for a dataset."""

  media_paths: list[PathTuple] = []
  markdown_paths: list[PathTuple] = []
  model_config = ConfigDict(extra='forbid')
  view_type: Literal['scroll', 'single_item'] = 'scroll'

  @field_validator('media_paths', mode='before')
  @classmethod
  def parse_media_paths(cls, media_paths: list) -> list:
    """Parse a path, ensuring it is a tuple."""
    return [normalize_path(path) for path in media_paths]

  @field_validator('markdown_paths', mode='before')
  @classmethod
  def parse_markdown_paths(cls, markdown_paths: list) -> list:
    """Parse a path, ensuring it is a tuple."""
    return [normalize_path(path) for path in markdown_paths]

  @field_serializer('media_paths')
  def serialize_media_paths(self, media_paths: list[PathTuple]) -> list[Union[str, list[str]]]:
    """Serialize media paths."""
    return [_serializable_path(path) for path in media_paths]

  @field_serializer('markdown_paths')
  def serialize_markdown_paths(
    self, markdown_paths: list[PathTuple]
  ) -> list[Union[str, list[str]]]:
    """Serialize markdown paths."""
    return [_serializable_path(path) for path in markdown_paths]


class DatasetSettings(BaseModel):
  """The persistent settings for a dataset."""

  ui: Optional[DatasetUISettings] = None
  preferred_embedding: Optional[str] = DEFAULT_EMBEDDING
  model_config = ConfigDict(extra='forbid')
  tags: Optional[list[str]] = PydanticField(
    description='A list of tags for the dataset to organize in the UI.', default=[]
  )


class DatasetConfig(BaseModel):
  """Configures a dataset with a source and transformations."""

  namespace: str = PydanticField(description='The namespace of the dataset.')
  name: str = PydanticField(description='The name of the dataset.')

  # Deprecated.
  tags: Optional[list[str]] = PydanticField(
    description='[Deprecated] This field is *deprecated* in favor of DatasetSettings.tags and '
    'will be removed in a later release.',
    default=[],
  )

  # The source configuration.
  source: SerializeAsAny[Source] = PydanticField(
    description='The source configuration. This config determines where data is loaded '
    'from for the dataset.'
  )

  # Model configuration: embeddings and signals on paths.
  embeddings: list[EmbeddingConfig] = PydanticField(
    description='The embedding configs for the dataset.', default=[]
  )

  # When defined, uses this list of signals instead of running all signals.
  signals: list[SignalConfig] = PydanticField(
    description='The signal configs for the dataset', default=[]
  )

  # Dataset settings, default embeddings and UI settings like media paths.
  settings: Optional[DatasetSettings] = PydanticField(description='Dataset settings.', default=None)
  model_config = ConfigDict(extra='forbid')

  @field_validator('source', mode='before')
  @classmethod
  def parse_source(cls, source: dict) -> Source:
    """Parse a source to its specific subclass instance."""
    return resolve_source(source)


class Config(BaseModel):
  """Configures a set of datasets for a lilac instance."""

  datasets: list[DatasetConfig] = PydanticField(
    description='The configurations for the datasets in the project.', default=[]
  )

  # When defined, uses this list of signals to run over every dataset, over all media paths, unless
  # signals is overridden by a specific dataset.
  signals: list[Signal] = PydanticField(
    description='The signals to run for every dataset.', default=[]
  )

  # A list of embeddings to compute the model caches for, for all concepts.
  concept_model_cache_embeddings: list[str] = PydanticField(
    description='The set of embeddings to compute model caches for for every concept.', default=[]
  )
  model_config = ConfigDict(extra='forbid')

  @field_validator('signals', mode='before')
  @classmethod
  def parse_signal(cls, signals: list[dict]) -> list[Signal]:
    """Parse alist of signals to their specific subclass instances."""
    return [resolve_signal(signal) for signal in signals]


def get_dataset_config(
  config: Config, dataset_namespace: str, dataset_name: str
) -> Optional[DatasetConfig]:
  """Returns the dataset config."""
  for dataset_config in config.datasets:
    if dataset_config.namespace == dataset_namespace and dataset_config.name == dataset_name:
      return dataset_config

  return None


def read_config(config_path: Union[str, pathlib.Path]) -> Config:
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
      raise ValueError('Config is not a valid `Config` or `DatasetConfig`') from error
  assert config is not None

  return config
