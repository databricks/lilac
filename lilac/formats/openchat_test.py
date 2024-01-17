"""Tests for the openchat format."""


from ..data.dataset_test_utils import TestDataMaker
from .openchat import OpenChat


def test_infer_open_chat(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data(
    [
      {
        'items': [
          {'role': 'user', 'content': 'Hello', 'weight': 0.0},
          {'role': 'assistant', 'content': 'Hi', 'weight': 1.0},
          {'role': 'user', 'content': 'How are you today?', 'weight': 0.0},
          {'role': 'assistant', 'content': "I'm fine.", 'weight': 1.0},
        ],
        'system': '',
      },
      {
        'items': [
          {'role': 'user', 'content': 'Who are you?', 'weight': 0.0},
          {'role': 'assistant', 'content': "I'm OpenChat.", 'weight': 1.0},
        ],
        'system': 'You are a helpful assistant named OpenChat.',
      },
    ]
  )

  assert dataset.manifest().dataset_format == OpenChat()
