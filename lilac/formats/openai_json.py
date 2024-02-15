"""ShareGPT format."""

from typing import ClassVar

from ..dataset_format import DatasetFormat, DatasetFormatInputSelector
from ..schema import PATH_WILDCARD, VALUE_KEY, Item, PathTuple, Schema, schema


def _openai_selector(item: Item, conv_role: str) -> str:
  """Selector for OpenAI JSON Formatted conversations."""
  # TODO(nsthorat): Make this return an array, and not pre-join with newlines.
  values = [conv['content'] for conv in item['messages'] if conv['role'] == conv_role]
  # Get the __value__ key version of text if it's enriched.
  values = [value if isinstance(value, str) else value.get(VALUE_KEY) for value in values]
  return '\n'.join(values)


_USER_SELECTOR = DatasetFormatInputSelector(
  name='user',
  selector=lambda item: _openai_selector(item, 'user'),
)

_ASSISTANT_SELECTOR = DatasetFormatInputSelector(
  name='assistant',
  selector=lambda item: _openai_selector(item, 'assistant'),
)


class OpenAIJSON(DatasetFormat):
  """OpenAI JSON format.

  Taken from: https://platform.openai.com/docs/api-reference/chat
  """

  name: ClassVar[str] = 'OpenAI JSON'
  data_schema: Schema = schema(
    {
      'messages': [
        {
          'role': 'string',
          'content': 'string',
        }
      ],
    },
  )

  title_slots: list[tuple[PathTuple, PathTuple]] = [
    (('messages', PATH_WILDCARD, 'content'), ('messages', PATH_WILDCARD, 'role'))
  ]

  user: ClassVar[DatasetFormatInputSelector] = _USER_SELECTOR
  assistant: ClassVar[DatasetFormatInputSelector] = _ASSISTANT_SELECTOR

  input_selectors: ClassVar[dict[str, DatasetFormatInputSelector]] = {
    selector.name: selector for selector in [_USER_SELECTOR, _ASSISTANT_SELECTOR]
  }


# TODO(nsthorat): Generalize this code so that 'conversations' or 'messages' can be the root field.
# This is the only difference that forces us to make a new format.


def _openai_conversation_selector(item: Item, conv_role: str) -> str:
  """Selector for OpenAI JSON Formatted conversations."""
  # TODO(nsthorat): Make this return an array, and not pre-join with newlines.
  values = [conv['content'] for conv in item['conversation'] if conv['role'] == conv_role]
  # Get the __value__ key version of text if it's enriched.
  values = [value if isinstance(value, str) else value.get(VALUE_KEY) for value in values]
  return '\n'.join(values)


_USER_CONVERSATION_SELECTOR = DatasetFormatInputSelector(
  name='user',
  selector=lambda item: _openai_conversation_selector(item, 'user'),
)

_ASSISTANT_CONVERSATION_SELECTOR = DatasetFormatInputSelector(
  name='assistant',
  selector=lambda item: _openai_conversation_selector(item, 'assistant'),
)


class OpenAIConversationJSON(DatasetFormat):
  """OpenAI JSON format.

  Taken from: https://platform.openai.com/docs/api-reference/chat

  Note that here "messages" is "conversation" for support with common datasets.
  """

  name: ClassVar[str] = 'OpenAI Conversation JSON'
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

  user: ClassVar[DatasetFormatInputSelector] = _USER_CONVERSATION_SELECTOR
  assistant: ClassVar[DatasetFormatInputSelector] = _ASSISTANT_CONVERSATION_SELECTOR

  input_selectors: ClassVar[dict[str, DatasetFormatInputSelector]] = {
    selector.name: selector
    for selector in [_USER_CONVERSATION_SELECTOR, _ASSISTANT_CONVERSATION_SELECTOR]
  }
