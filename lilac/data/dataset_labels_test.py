"""Tests for dataset.compute_signal()."""

from datetime import datetime

from freezegun import freeze_time
from pytest_mock import MockerFixture

from ..schema import PATH_WILDCARD, ROWID, Item, field, schema
from .dataset import DatasetManifest, SelectGroupsResult
from .dataset_test_utils import TestDataMaker, TestSource

TEST_ITEMS: list[Item] = [
  {
    'str': 'a',
    'int': 1
  },
  {
    'str': 'b',
    'int': 2
  },
  {
    'str': 'c',
    'int': 2
  },
]

TEST_TIME = '2023-08-15 01:23:45'


@freeze_time(TEST_TIME)
def test_add_single_label(make_test_data: TestDataMaker, mocker: MockerFixture) -> None:
  test_datetime = datetime.now()
  mock_datetime = mocker.patch.object(datetime, 'now', autospec=True)
  mock_datetime.return_value = test_datetime

  dataset = make_test_data(TEST_ITEMS)

  dataset.add_labels('test_label', 'yes', filters=[(ROWID, 'equals', '1')])

  assert dataset.manifest() == DatasetManifest(
    source=TestSource(),
    namespace='test_namespace',
    dataset_name='test_dataset',
    data_schema=schema({
      'str': 'string',
      'int': 'int32',
      'test_label': field(fields={
        'label': 'string',
        'created': 'timestamp'
      }, label='test_label')
    }),
    num_items=3)

  assert list(dataset.select_rows([PATH_WILDCARD])) == [{
    'str': 'a',
    'int': 1,
    'test_label': {
      'label': 'yes',
      'created': '2023-08-15T01:23:45'
    }
  }, {
    'str': 'b',
    'int': 2,
    'test_label': None
  }, {
    'str': 'c',
    'int': 2,
    'test_label': None
  }]

  # Make sure we can filter by the label.
  assert list(
    dataset.select_rows([PATH_WILDCARD], filters=[('test_label.label', 'equals', 'yes')])) == [{
      'str': 'a',
      'int': 1,
      'test_label': {
        'label': 'yes',
        'created': '2023-08-15T01:23:45'
      }
    }]


@freeze_time(TEST_TIME)
def test_add_multiple_labels(make_test_data: TestDataMaker, mocker: MockerFixture) -> None:
  test_datetime = datetime.now()
  mock_datetime = mocker.patch.object(datetime, 'now', autospec=True)
  mock_datetime.return_value = test_datetime

  dataset = make_test_data(TEST_ITEMS)

  # Add a 'yes' for every item with int=2.
  dataset.add_labels('test_label', 'yes', filters=[('int', 'equals', 2)])
  # Add a 'no' for every item with int < 2.
  dataset.add_labels('test_label', 'no', filters=[('int', 'less', 2)])

  assert dataset.manifest() == DatasetManifest(
    source=TestSource(),
    namespace='test_namespace',
    dataset_name='test_dataset',
    data_schema=schema({
      'str': 'string',
      'int': 'int32',
      'test_label': field(fields={
        'label': 'string',
        'created': 'timestamp'
      }, label='test_label')
    }),
    num_items=3)

  assert list(dataset.select_rows([PATH_WILDCARD])) == [{
    'str': 'a',
    'int': 1,
    'test_label': {
      'label': 'no',
      'created': '2023-08-15T01:23:45'
    }
  }, {
    'str': 'b',
    'int': 2,
    'test_label': {
      'label': 'yes',
      'created': '2023-08-15T01:23:45'
    }
  }, {
    'str': 'c',
    'int': 2,
    'test_label': {
      'label': 'yes',
      'created': '2023-08-15T01:23:45'
    }
  }]


@freeze_time(TEST_TIME)
def test_labels_select_groups(make_test_data: TestDataMaker, mocker: MockerFixture) -> None:
  test_datetime = datetime.now()
  mock_datetime = mocker.patch.object(datetime, 'now', autospec=True)
  mock_datetime.return_value = test_datetime

  dataset = make_test_data(TEST_ITEMS)

  # Add a 'yes' for every item with int=2.
  dataset.add_labels('test_label', 'yes', filters=[('int', 'equals', 2)])
  # Add a 'no' for every item with int < 2.
  dataset.add_labels('test_label', 'no', filters=[('int', 'less', 2)])

  assert dataset.select_groups(('test_label', 'label')) == SelectGroupsResult(
    too_many_distinct=False, counts=[('yes', 2), ('no', 1)])
