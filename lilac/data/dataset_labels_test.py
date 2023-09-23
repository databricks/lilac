"""Tests for dataset.compute_signal()."""

from datetime import datetime
from typing import Iterable

import pytest
from freezegun import freeze_time
from pytest_mock import MockerFixture

from lilac.sources.source_registry import clear_source_registry, register_source

from ..schema import PATH_WILDCARD, ROWID, Item, field, schema
from .dataset import DatasetManifest, SelectGroupsResult, SortOrder
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
    'int': 3
  },
]

TEST_TIME = datetime(2023, 8, 15, 1, 23, 45)


@pytest.fixture(scope='module', autouse=True)
def setup_teardown() -> Iterable[None]:
  # Setup.
  register_source(TestSource)

  # Unit test runs.
  yield

  # Teardown.
  clear_source_registry()


@freeze_time(TEST_TIME)
def test_add_single_label(make_test_data: TestDataMaker, mocker: MockerFixture) -> None:
  test_datetime = datetime.now()
  mock_datetime = mocker.patch.object(datetime, 'now', autospec=True)
  mock_datetime.return_value = test_datetime

  dataset = make_test_data(TEST_ITEMS)

  dataset.add_labels('test_label', filters=[(ROWID, 'equals', '1')])

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
      'label': 'true',
      'created': TEST_TIME
    }
  }, {
    'str': 'b',
    'int': 2,
    'test_label': None
  }, {
    'str': 'c',
    'int': 3,
    'test_label': None
  }]

  # Make sure we can filter by the label.
  assert list(
    dataset.select_rows([PATH_WILDCARD], filters=[('test_label.label', 'equals', 'true')])) == [{
      'str': 'a',
      'int': 1,
      'test_label': {
        'label': 'true',
        'created': TEST_TIME
      }
    }]


@freeze_time(TEST_TIME)
def test_add_row_labels(make_test_data: TestDataMaker, mocker: MockerFixture) -> None:
  test_datetime = datetime.now()
  mock_datetime = mocker.patch.object(datetime, 'now', autospec=True)
  mock_datetime.return_value = test_datetime

  dataset = make_test_data(TEST_ITEMS)

  dataset.add_labels('test_label', row_ids=['1', '2'])

  assert list(dataset.select_rows([PATH_WILDCARD])) == [{
    'str': 'a',
    'int': 1,
    'test_label': {
      'label': 'true',
      'created': TEST_TIME
    }
  }, {
    'str': 'b',
    'int': 2,
    'test_label': {
      'label': 'true',
      'created': TEST_TIME
    }
  }, {
    'str': 'c',
    'int': 3,
    'test_label': None
  }]


@freeze_time(TEST_TIME)
def test_add_row_labels_no_filters(make_test_data: TestDataMaker, mocker: MockerFixture) -> None:
  test_datetime = datetime.now()
  mock_datetime = mocker.patch.object(datetime, 'now', autospec=True)
  mock_datetime.return_value = test_datetime

  dataset = make_test_data(TEST_ITEMS)

  dataset.add_labels('test_label')

  assert list(dataset.select_rows([PATH_WILDCARD])) == [{
    'str': 'a',
    'int': 1,
    'test_label': {
      'label': 'true',
      'created': TEST_TIME
    }
  }, {
    'str': 'b',
    'int': 2,
    'test_label': {
      'label': 'true',
      'created': TEST_TIME
    }
  }, {
    'str': 'c',
    'int': 3,
    'test_label': {
      'label': 'true',
      'created': TEST_TIME
    }
  }]


@freeze_time(TEST_TIME)
def test_remove_labels(make_test_data: TestDataMaker, mocker: MockerFixture) -> None:
  test_datetime = datetime.now()
  mock_datetime = mocker.patch.object(datetime, 'now', autospec=True)
  mock_datetime.return_value = test_datetime

  dataset = make_test_data(TEST_ITEMS)

  dataset.add_labels('test_label', row_ids=['1', '2', '3'])
  # Remove the first label.
  dataset.remove_labels('test_label', row_ids=['1'])

  assert list(dataset.select_rows([PATH_WILDCARD], sort_by=['int'], sort_order=SortOrder.ASC)) == [{
    'str': 'a',
    'int': 1,
    'test_label': None
  }, {
    'str': 'b',
    'int': 2,
    'test_label': {
      'label': 'true',
      'created': TEST_TIME
    }
  }, {
    'str': 'c',
    'int': 3,
    'test_label': {
      'label': 'true',
      'created': TEST_TIME
    }
  }]

  # Remove by a filter.
  dataset.remove_labels('test_label', filters=[('int', 'greater_equal', 2)])
  assert list(dataset.select_rows([PATH_WILDCARD], sort_by=['int'], sort_order=SortOrder.ASC)) == [{
    'str': 'a',
    'int': 1,
    'test_label': None
  }, {
    'str': 'b',
    'int': 2,
    'test_label': None
  }, {
    'str': 'c',
    'int': 3,
    'test_label': None
  }]


@freeze_time(TEST_TIME)
def test_remove_labels_no_filters(make_test_data: TestDataMaker, mocker: MockerFixture) -> None:
  test_datetime = datetime.now()
  mock_datetime = mocker.patch.object(datetime, 'now', autospec=True)
  mock_datetime.return_value = test_datetime

  dataset = make_test_data(TEST_ITEMS)

  # Add all labels.
  dataset.add_labels('test_label')
  # Remove all labels.
  dataset.remove_labels('test_label')

  assert list(dataset.select_rows([PATH_WILDCARD], sort_by=['int'], sort_order=SortOrder.ASC)) == [{
    'str': 'a',
    'int': 1,
    'test_label': None
  }, {
    'str': 'b',
    'int': 2,
    'test_label': None
  }, {
    'str': 'c',
    'int': 3,
    'test_label': None
  }]


@freeze_time(TEST_TIME)
def test_label_overwrites(make_test_data: TestDataMaker, mocker: MockerFixture) -> None:
  test_datetime = datetime.now()
  mock_datetime = mocker.patch.object(datetime, 'now', autospec=True)
  mock_datetime.return_value = test_datetime

  dataset = make_test_data(TEST_ITEMS)

  dataset.add_labels('test_label', value='yes', filters=[(ROWID, 'equals', '1')])
  # Overwrite the value.
  dataset.add_labels('test_label', value='no', filters=[(ROWID, 'equals', '1')])

  assert list(dataset.select_rows([PATH_WILDCARD])) == [{
    'str': 'a',
    'int': 1,
    'test_label': {
      'label': 'no',
      'created': TEST_TIME
    }
  }, {
    'str': 'b',
    'int': 2,
    'test_label': None
  }, {
    'str': 'c',
    'int': 3,
    'test_label': None
  }]


@freeze_time(TEST_TIME)
def test_add_multiple_labels(make_test_data: TestDataMaker, mocker: MockerFixture) -> None:
  test_datetime = datetime.now()
  mock_datetime = mocker.patch.object(datetime, 'now', autospec=True)
  mock_datetime.return_value = test_datetime

  dataset = make_test_data(TEST_ITEMS)

  # Add a 'yes' for every item with int=2.
  dataset.add_labels('test_label', value='yes', filters=[('int', 'greater_equal', 2)])
  # Add a 'no' for every item with int < 2.
  dataset.add_labels('test_label', value='no', filters=[('int', 'less', 2)])

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
      'created': TEST_TIME
    }
  }, {
    'str': 'b',
    'int': 2,
    'test_label': {
      'label': 'yes',
      'created': TEST_TIME
    }
  }, {
    'str': 'c',
    'int': 3,
    'test_label': {
      'label': 'yes',
      'created': TEST_TIME
    }
  }]


@freeze_time(TEST_TIME)
def test_labels_select_groups(make_test_data: TestDataMaker, mocker: MockerFixture) -> None:
  test_datetime = datetime.now()
  mock_datetime = mocker.patch.object(datetime, 'now', autospec=True)
  mock_datetime.return_value = test_datetime

  dataset = make_test_data(TEST_ITEMS)

  # Add a 'yes' for every item with int=2.
  dataset.add_labels('test_label', value='yes', filters=[('int', 'greater_equal', 2)])
  # Add a 'no' for every item with int < 2.
  dataset.add_labels('test_label', value='no', filters=[('int', 'less', 2)])

  assert dataset.select_groups(('test_label', 'label')) == SelectGroupsResult(
    too_many_distinct=False, counts=[('yes', 2), ('no', 1)])
