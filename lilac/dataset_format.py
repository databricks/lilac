"""Utilities for inferring dataset formats.

Formats are taken from axlotl: https://github.com/OpenAccess-AI-Collective/axolotl#dataset
"""

import copy
from typing import Any, Callable, ClassVar, Optional, Type, Union

from pydantic import BaseModel, ConfigDict, model_serializer

from .schema import Item, PathTuple, Schema


class DatasetFormatInputSelector(BaseModel):
  """Input lambda selectors that map an item to a string, used for format-specific runtime filters.

  For example, in the ShareGPT format, we want 'human' to only filter conversations
  where conversations.*.from='human'.
  """

  name: str
  selector: Callable[[Item], str]


class DatasetFormat(BaseModel):
  """A dataset format.

  Formats are taken from: https://github.com/OpenAccess-AI-Collective/axolotl#dataset.

  Formats allow us to specify opinionated selectors, like selecting only "human" parts of
  conversations. They also allow us to specify title slots, which are used to display
  titles over certain media fields in the UI.
  """

  # Allow extra fields for dataset formats.
  model_config = ConfigDict(extra='allow')

  name: ClassVar[str]
  data_schema: Optional[Schema] = None

  # Title slots are a mapping of a media path to a path that represents the title to be displayed
  # for that media path. This allows us to put a title over certain media fields in the UI.
  title_slots: Optional[list[tuple[PathTuple, PathTuple]]] = []

  # Input selectors are used for format-specific runtime filters.
  input_selectors: ClassVar[dict[str, DatasetFormatInputSelector]] = {}

  @model_serializer(mode='wrap', when_used='always')
  def serialize_model(self, serializer: Callable[..., dict[str, Any]]) -> dict[str, Any]:
    """Serialize the model to a dictionary."""
    res = serializer(self)
    res['format_name'] = self.name
    return res


def schema_is_compatible_with(dataset_schema: Schema, format_schema: Schema) -> bool:
  """Returns true if all fields of the format schema are in the dataset schema."""
  for path, field in format_schema.all_fields:
    if not dataset_schema.has_field(path):
      return False

    field = dataset_schema.get_field(path)
    if field.dtype != format_schema.get_field(path).dtype:
      return False

  return True


DATASET_FORMAT_REGISTRY: dict[str, Type[DatasetFormat]] = {}


def infer_formats(data_schema: Schema) -> list[type[DatasetFormat]]:
  """Infer the dataset formats for a dataset."""
  formats = []
  for format_cls in DATASET_FORMAT_REGISTRY.values():
    format = format_cls()
    if format.data_schema and schema_is_compatible_with(data_schema, format.data_schema):
      formats.append(format_cls)
  return formats


def register_dataset_format(format_cls: Type[DatasetFormat]) -> None:
  """Register a dataset format in the global registry."""
  if format_cls.name in DATASET_FORMAT_REGISTRY:
    raise ValueError(f'Dataset format "{format_cls.name}" has already been registered!')

  DATASET_FORMAT_REGISTRY[format_cls.name] = format_cls


def get_dataset_format_cls(format_name: str) -> Optional[Type[DatasetFormat]]:
  """Return a registered dataset format class given the name in the registry."""
  return (
    DATASET_FORMAT_REGISTRY.get(format_name) if format_name in DATASET_FORMAT_REGISTRY else None
  )


def resolve_dataset_format(dataset_format: Union[dict, DatasetFormat]) -> DatasetFormat:
  """Resolve a generic format base class to a specific format class."""
  if isinstance(dataset_format, DatasetFormat):
    # The format is already parsed.
    return dataset_format

  format_name = dataset_format.get('format_name')
  if not format_name:
    raise ValueError('"dataset_format" needs to be defined in the json dict.')

  format_cls = get_dataset_format_cls(format_name)
  if not format_cls:
    # Make a metaclass so we get a valid `DatasetFormat` class.
    format_cls = type(f'DatasetFormat_{format_name}', (DatasetFormat,), {'name': format_name})

  dataset_format = copy.deepcopy(dataset_format)
  del dataset_format['dataset_format']
  return format_cls(**dataset_format)


def clear_dataset_format_registry() -> None:
  """Clear the format registry."""
  DATASET_FORMAT_REGISTRY.clear()
