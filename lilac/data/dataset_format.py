"""Utilities for inferring dataset formats."""

from typing import Callable, ClassVar

from pydantic import BaseModel, ConfigDict

from ..schema import PATH_WILDCARD, Item, PathTuple, Schema, schema


class DatasetFormat(BaseModel):
  """A dataset format."""

  # Allow extra fields for dataset formats.
  model_config = ConfigDict(extra='allow')

  name: str
  data_schema: Schema

  # Title slots are a mapping of a media path to a path that represents the title to be displayed
  # for that media path. This allows us to put a title over certain media fields in the UI.
  title_slots: list[tuple[PathTuple, PathTuple]] = []


class DatasetFormatInputSelector(BaseModel):
  """Input lambda selectors that map an item to a string, used for format-specific runtime filters.

  For example, in the ShareGPT format, we want 'human' to only filter conversations
  where conversations.*.from='human'.
  """

  name: str
  selector: Callable[[Item], str]


def _sharegpt_selector(item: Item, conv_from: str) -> str:
  """Selector for ShareGPT."""
  return '\n'.join(conv['value'] for conv in item['conversations'] if conv['from'] == conv_from)


class ShareGPTFormat(DatasetFormat):
  """ShareGPT format."""

  name: str = 'sharegpt'
  data_schema: Schema = schema(
    {
      'conversations': [
        {
          'from': 'string',
          'value': 'string',
        }
      ]
    }
  )
  title_slots: list[tuple[PathTuple, PathTuple]] = [
    (('conversations', PATH_WILDCARD, 'value'), ('conversations', PATH_WILDCARD, 'from'))
  ]
  human: ClassVar[DatasetFormatInputSelector] = DatasetFormatInputSelector(
    name='human',
    selector=lambda item: _sharegpt_selector(item, 'human'),
  )
  gpt: ClassVar[DatasetFormatInputSelector] = DatasetFormatInputSelector(
    name='gpt',
    selector=lambda item: _sharegpt_selector(item, 'gpt'),
  )
  system: ClassVar[DatasetFormatInputSelector] = DatasetFormatInputSelector(
    name='system',
    selector=lambda item: _sharegpt_selector(item, 'system'),
  )


ShareGPT = ShareGPTFormat()

# https://github.com/imoneoi/openchat
OpenChat = DatasetFormat(
  name='openchat_format',
  title_slots=[(('items', PATH_WILDCARD, 'content'), ('items', PATH_WILDCARD, 'role'))],
  data_schema=schema(
    {
      'items': [
        {
          'role': 'string',
          'content': 'string',
        }
      ],
      'system': 'string',
    },
  ),
)

# Formats are taken from axlotl: https://github.com/OpenAccess-AI-Collective/axolotl#dataset
DATASET_FORMATS: list[DatasetFormat] = [ShareGPT, OpenChat]


def schema_is_compatible_with(dataset_schema: Schema, format_schema: Schema) -> bool:
  """Returns true if all fields of the format schema are in the dataset schema."""
  for path, field in format_schema.all_fields:
    if not dataset_schema.has_field(path):
      return False

    field = dataset_schema.get_field(path)
    if field.dtype != format_schema.get_field(path).dtype:
      return False

  return True


def infer_formats(data_schema: Schema) -> list[DatasetFormat]:
  """Infer the dataset formats for a dataset."""
  formats = []
  for format in DATASET_FORMATS:
    if schema_is_compatible_with(data_schema, format.data_schema):
      formats.append(format)
  return formats
