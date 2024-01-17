"""ShareGPT format."""
from typing import ClassVar

from ..dataset_format import DatasetFormat, DatasetFormatInputSelector
from ..schema import PATH_WILDCARD, Item, PathTuple, Schema, schema


def _sharegpt_selector(item: Item, conv_from: str) -> str:
  """Selector for ShareGPT."""
  # TODO(nsthorat): Make this return an array, and not pre-join with newlines.
  return '\n'.join(conv['value'] for conv in item['conversations'] if conv['from'] == conv_from)


_SYSTEM_SELECTOR = DatasetFormatInputSelector(
  name='system',
  selector=lambda item: _sharegpt_selector(item, 'system'),
)
_HUMAN_SELECTOR = DatasetFormatInputSelector(
  name='human',
  selector=lambda item: _sharegpt_selector(item, 'human'),
)
_GPT_SELECTOR = DatasetFormatInputSelector(
  name='gpt',
  selector=lambda item: _sharegpt_selector(item, 'gpt'),
)


class ShareGPT(DatasetFormat):
  """ShareGPT format."""

  name: ClassVar[str] = 'sharegpt'
  data_schema: ClassVar[Schema] = schema(
    {
      'conversations': [
        {
          'from': 'string',
          'value': 'string',
        }
      ]
    }
  )
  title_slots: ClassVar[list[tuple[PathTuple, PathTuple]]] = [
    (('conversations', PATH_WILDCARD, 'value'), ('conversations', PATH_WILDCARD, 'from'))
  ]

  system: ClassVar[DatasetFormatInputSelector] = _SYSTEM_SELECTOR
  human: ClassVar[DatasetFormatInputSelector] = _HUMAN_SELECTOR
  gpt: ClassVar[DatasetFormatInputSelector] = _GPT_SELECTOR

  input_selectors: ClassVar[dict[str, DatasetFormatInputSelector]] = {
    selector.name: selector for selector in [_SYSTEM_SELECTOR, _HUMAN_SELECTOR, _GPT_SELECTOR]
  }
