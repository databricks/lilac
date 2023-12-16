"""Utilities for inferring dataset formats."""

from pydantic import BaseModel

from ..schema import PATH_WILDCARD, PathTuple, Schema, schema


class DatasetFormat(BaseModel):
  """A dataset format."""

  name: str
  data_schema: Schema

  # Title slots are a mapping of a media path to a path that represents the title to be displayed
  # for that media path. This allows us to put a title over certain media fields in the UI.
  title_slots: list[tuple[PathTuple, PathTuple]] = []


SHARE_GPT_FORMAT = DatasetFormat(
  name='sharegpt',
  title_slots=[
    (('conversations', PATH_WILDCARD, 'value'), ('conversations', PATH_WILDCARD, 'from'))
  ],
  data_schema=schema(
    {
      'conversations': [
        {
          'from': 'string',
          'value': 'string',
        }
      ]
    }
  ),
)

# https://github.com/imoneoi/openchat
OPEN_CHAT_FORMAT = DatasetFormat(
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
DATASET_FORMATS: list[DatasetFormat] = [SHARE_GPT_FORMAT, OPEN_CHAT_FORMAT]


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
