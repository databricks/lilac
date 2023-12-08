"""Tests for the dataset_format module."""


from .dataset_format import SHARE_GPT_FORMAT, infer_formats
from .dataset_test_utils import TestDataMaker


def test_infer_sharegpt(make_test_data: TestDataMaker):
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

  assert infer_formats(dataset.manifest().data_schema) == [SHARE_GPT_FORMAT]


def test_infer_sharegpt_extra(make_test_data: TestDataMaker):
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

  assert infer_formats(dataset.manifest().data_schema) == [SHARE_GPT_FORMAT]
