"""ShareGPT format."""
from typing import ClassVar

from ..dataset_format import DatasetFormat, DatasetFormatInputSelector
from ..schema import PATH_WILDCARD, VALUE_KEY, Item, PathTuple, Schema, schema


def _sharegpt_selector(item: Item, conv_from: str) -> str:
  """Selector for ShareGPT."""
  # TODO(nsthorat): Make this return an array, and not pre-join with newlines.
  values = [conv['value'] for conv in item['conversations'] if conv['from'] == conv_from]

  # Get the __value__ key version of text if it's enriched.
  values = [value if isinstance(value, str) else value.get(VALUE_KEY) for value in values]

  return '\n'.join(values)


_SYSTEM_SELECTOR = DatasetFormatInputSelector(
  name='system',
  selector=lambda item: _sharegpt_selector(item, 'system'),
)
_HUMAN_SELECTOR = DatasetFormatInputSelector(
  name='human',
  selector=lambda item: _sharegpt_selector(item, 'human'),
)
_TOOL_SELECTOR = DatasetFormatInputSelector(
  name='tool',
  selector=lambda item: _sharegpt_selector(item, 'tool'),
)
_GPT_SELECTOR = DatasetFormatInputSelector(
  name='gpt',
  selector=lambda item: _sharegpt_selector(item, 'gpt'),
)


class ShareGPT(DatasetFormat):
  """ShareGPT format."""

  name: ClassVar[str] = 'sharegpt'
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

  system: ClassVar[DatasetFormatInputSelector] = _SYSTEM_SELECTOR
  human: ClassVar[DatasetFormatInputSelector] = _HUMAN_SELECTOR
  tool: ClassVar[DatasetFormatInputSelector] = _TOOL_SELECTOR
  gpt: ClassVar[DatasetFormatInputSelector] = _GPT_SELECTOR

  input_selectors: ClassVar[dict[str, DatasetFormatInputSelector]] = {
    selector.name: selector
    for selector in [_SYSTEM_SELECTOR, _HUMAN_SELECTOR, _GPT_SELECTOR, _TOOL_SELECTOR]
  }
