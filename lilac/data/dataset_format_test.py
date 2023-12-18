"""Tests for the dataset_format module."""


from .dataset_format import OPEN_CHAT_FORMAT, SHARE_GPT_FORMAT
from .dataset_test_utils import TestDataMaker


def test_infer_sharegpt(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data(
    [
      {
        'conversations': [
          {'from': 'system', 'value': 'You are a language model.'},
          {'from': 'human', 'value': 'hello'},
        ]
      },
      {'conversations': [{'from': 'human', 'value': 'Hello again'}]},
    ]
  )

  assert dataset.manifest().dataset_format == SHARE_GPT_FORMAT


def test_infer_sharegpt_extra(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data(
    [
      {
        'conversations': [
          {'from': 'system', 'value': 'You are a language model.'},
          {'from': 'human', 'value': 'hello'},
        ],
        'extra': 2,
      },
      {'conversations': [{'from': 'human', 'value': 'Hello again'}], 'extra': 1},
    ]
  )

  assert dataset.manifest().dataset_format == SHARE_GPT_FORMAT


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

  assert dataset.manifest().dataset_format == OPEN_CHAT_FORMAT


def test_other_format(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data(
    [
      {'extra': 2, 'question': 'hello?'},
      {'extra': 1, 'question': 'anybody?'},
    ]
  )

  assert dataset.manifest().dataset_format is None
