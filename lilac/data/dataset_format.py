"""Utilities for inferring dataset formats."""

from pydantic import BaseModel

from ..schema import Schema, schema


class DatasetFormat(BaseModel):
  """A dataset format."""

  name: str
  data_schema: Schema


SHARE_GPT_FORMAT = DatasetFormat(
  name='sharegpt',
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

# Formats are taken from axlotl: https://github.com/OpenAccess-AI-Collective/axolotl#dataset
DATASET_FORMATS: list[DatasetFormat] = [SHARE_GPT_FORMAT]


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
