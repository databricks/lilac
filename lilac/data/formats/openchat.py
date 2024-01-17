"""ShareGPT format."""

from typing import ClassVar

from ...schema import PATH_WILDCARD, PathTuple, Schema, schema
from ..dataset_format import DatasetFormat


# https://github.com/imoneoi/openchat
class OpenChat(DatasetFormat):
  """OpenChat format."""

  name: ClassVar[str] = 'openchat'
  data_schema: ClassVar[Schema] = schema(
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

  title_slots: ClassVar[list[tuple[PathTuple, PathTuple]]] = [
    (('items', PATH_WILDCARD, 'content'), ('items', PATH_WILDCARD, 'role'))
  ]
