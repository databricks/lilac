"""Tests for dataset.settings and dataset.update_settings."""

from ..schema import UUID_COLUMN, Item
from .dataset import DatasetSettings, DatasetUISettings
from .dataset_test_utils import TestDataMaker

SIMPLE_ITEMS: list[Item] = [{
  UUID_COLUMN: '1',
  'str': 'a',
  'int': 1,
  'bool': False,
  'float': 3.0,
  'long_str': 'a' * 32
}, {
  UUID_COLUMN: '2',
  'str': 'b',
  'int': 2,
  'bool': True,
  'float': 2.0,
  'long_str': 'b' * 32
}, {
  UUID_COLUMN: '3',
  'str': 'b',
  'int': 2,
  'bool': True,
  'float': 1.0,
  'long_str': 'c' * 32
}]


def test_settings(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data(SIMPLE_ITEMS)

  assert dataset.settings() == DatasetSettings(ui=DatasetUISettings(media_paths=[['long_str']]))

  dataset.update_settings(DatasetSettings(ui=DatasetUISettings(media_paths=[['str']])))

  assert dataset.settings() == DatasetSettings(ui=DatasetUISettings(media_paths=[['str']]))
