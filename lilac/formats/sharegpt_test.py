"""Tests for inferring the sharegpt format."""


from ..data.dataset_test_utils import TestDataMaker
from .sharegpt import ShareGPT


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

  assert dataset.manifest().dataset_format == ShareGPT()


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

  assert dataset.manifest().dataset_format == ShareGPT()


def test_human_selector(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data(
    [
      {
        'conversations': [
          {'from': 'system', 'value': 'You are a language model.'},
          {'from': 'human', 'value': 'hello'},
          {'from': 'gpt', 'value': 'hello'},
        ]
      },
      {
        'conversations': [
          {'from': 'human', 'value': 'Hello again'},
          {'from': 'gpt', 'value': 'Hello'},
        ]
      },
      {'conversations': [{'from': 'gpt', 'value': 'i am an ai'}]},
    ]
  )

  assert list(dataset.map(map_fn=ShareGPT.system.selector)) == ['You are a language model.', '', '']
  assert list(dataset.map(map_fn=ShareGPT.human.selector)) == ['hello', 'Hello again', '']
  assert list(dataset.map(map_fn=ShareGPT.gpt.selector)) == ['hello', 'Hello', 'i am an ai']

  assert list(dataset.map(map_fn=ShareGPT.input_selectors['system'].selector)) == list(
    dataset.map(map_fn=ShareGPT.system.selector)
  )
  assert list(dataset.map(map_fn=ShareGPT.input_selectors['human'].selector)) == list(
    dataset.map(map_fn=ShareGPT.human.selector)
  )
  assert list(dataset.map(map_fn=ShareGPT.input_selectors['gpt'].selector)) == list(
    dataset.map(map_fn=ShareGPT.gpt.selector)
  )
