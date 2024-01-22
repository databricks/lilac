"""ShareGPT format."""

from typing import ClassVar

from ..dataset_format import DatasetFormat, DatasetFormatInputSelector
from ..schema import PATH_WILDCARD, VALUE_KEY, Item, PathTuple, Schema, schema


def _openai_selector(item: Item, conv_role: str) -> str:
  """Selector for OpenAI JSON Formatted conversations."""
  # TODO(nsthorat): Make this return an array, and not pre-join with newlines.
  values = [conv['content'] for conv in item['conversation'] if conv['role'] == conv_role]
  # Get the __value__ key version of text if it's enriched.
  values = [value.get(VALUE_KEY, value) for value in values]
  return '\n'.join(values)


_USER_SELECTOR = DatasetFormatInputSelector(
  name='user',
  selector=lambda item: _openai_selector(item, 'user'),
)


class OpenAIJSON(DatasetFormat):
  """OpenAI JSON format.

  Taken from: https://platform.openai.com/docs/api-reference/chat

  Note that here "messages" is "conversation" for support with common datasets.
  """

  name: ClassVar[str] = 'openai_json'
  data_schema: Schema = schema(
    {
      'conversation': [
        {
          'role': 'string',
          'content': 'string',
        }
      ],
    },
  )

  title_slots: list[tuple[PathTuple, PathTuple]] = [
    (('conversation', PATH_WILDCARD, 'content'), ('conversation', PATH_WILDCARD, 'role'))
  ]

  user: ClassVar[DatasetFormatInputSelector] = _USER_SELECTOR

  input_selectors: ClassVar[dict[str, DatasetFormatInputSelector]] = {
    selector.name: selector for selector in [_USER_SELECTOR]
  }
