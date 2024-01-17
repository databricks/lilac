"""ShareGPT format."""

from ...schema import PATH_WILDCARD, schema
from ..dataset_format import DatasetFormat


# https://github.com/imoneoi/openchat
class OpenChat(DatasetFormat):
  """OpenChat format."""

  name = 'openchat'
  data_schema = schema(
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

  title_slots = [(('items', PATH_WILDCARD, 'content'), ('items', PATH_WILDCARD, 'role'))]
