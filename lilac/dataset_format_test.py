"""Tests for the dataset_format module."""


from .data.dataset_test_utils import TestDataMaker


def test_infer_no_format(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data(
    [
      {'extra': 2, 'question': 'hello?'},
      {'extra': 1, 'question': 'anybody?'},
    ]
  )

  assert dataset.manifest().dataset_format is None
