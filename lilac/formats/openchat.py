"""ShareGPT format."""

from typing import ClassVar

from ..dataset_format import DatasetFormat
from ..schema import PATH_WILDCARD, PathTuple, Schema, schema


# https://github.com/imoneoi/openchat
class OpenChat(DatasetFormat):
  """OpenChat format."""

  name: ClassVar[str] = 'openchat'
  data_schema: Schema = schema(
    {
      'items': [
        {
          'role': 'string',
          'content': 'string',
        }
      ],
      'system': 'string',
    },
  )

  title_slots: list[tuple[PathTuple, PathTuple]] = [
    (('items', PATH_WILDCARD, 'content'), ('items', PATH_WILDCARD, 'role'))
  ]
