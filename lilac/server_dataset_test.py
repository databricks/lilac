"""Test our public REST API."""
import os
from typing import Iterable, Optional, Type

import pytest
from fastapi.testclient import TestClient
from pytest_mock import MockerFixture

from .config import DatasetSettings
from .data.dataset import Dataset, DatasetManifest, SelectRowsSchemaResult, SelectRowsSchemaUDF
from .data.dataset_duckdb import DatasetDuckDB
from .data.dataset_test_utils import TEST_DATASET_NAME, TEST_NAMESPACE, enriched_item, make_dataset
from .router_dataset import (
  Column,
  ComputeSignalOptions,
  DeleteSignalOptions,
  SelectRowsOptions,
  SelectRowsResponse,
  SelectRowsSchemaOptions,
  WebManifest,
)
from .schema import Field, Item, RichData, field, schema
from .server import app
from .signal import TextSignal, clear_signal_registry, register_signal

client = TestClient(app)

DATASET_CLASSES = [DatasetDuckDB]

TEST_DATA: list[Item] = [{
  'erased': False,
  'people': [{
    'name': 'A',
    'zipcode': 0,
    'locations': [{
      'city': 'city1',
      'state': 'state1'
    }, {
      'city': 'city2',
      'state': 'state2'
    }]
  }]
}, {
  'erased': True,
  'people': [{
    'name': 'B',
    'zipcode': 1,
    'locations': [{
      'city': 'city3',
      'state': 'state3'
    }, {
      'city': 'city4'
    }, {
      'city': 'city5'
    }]
  }, {
    'name': 'C',
    'zipcode': 2,
    'locations': [{
      'city': 'city1',
      'state': 'state1'
    }]
  }]
}, {
  'erased': True
}]


@pytest.fixture(scope='module', autouse=True)
def setup_teardown() -> Iterable[None]:
  # Setup.
  register_signal(LengthSignal)
  # Unit test runs.
  yield
  # Teardown.
  clear_signal_registry()


@pytest.fixture(scope='module', autouse=True, params=DATASET_CLASSES)
def test_data(tmp_path_factory: pytest.TempPathFactory, module_mocker: MockerFixture,
              request: pytest.FixtureRequest) -> None:
  tmp_path = tmp_path_factory.mktemp('data')
  module_mocker.patch.dict(os.environ, {'LILAC_DATA_PATH': str(tmp_path)})

  dataset_cls: Type[Dataset] = request.param
  make_dataset(dataset_cls, tmp_path, TEST_DATA)


def test_get_manifest() -> None:
  url = f'/api/v1/datasets/{TEST_NAMESPACE}/{TEST_DATASET_NAME}'
  response = client.get(url)
  assert response.status_code == 200
  assert WebManifest.parse_obj(response.json()) == WebManifest(
    dataset_manifest=DatasetManifest(
      namespace=TEST_NAMESPACE,
      dataset_name=TEST_DATASET_NAME,
      data_schema=schema({
        'erased': 'boolean',
        'people': [{
          'name': 'string',
          'zipcode': 'int32',
          'locations': [{
            'city': 'string',
            'state': 'string'
          }]
        }]
      }),
      num_items=3))


def test_select_rows_no_options() -> None:
  url = f'/api/v1/datasets/{TEST_NAMESPACE}/{TEST_DATASET_NAME}/select_rows'
  options = SelectRowsOptions()
  response = client.post(url, json=options.dict())
  assert response.status_code == 200
  assert SelectRowsResponse.parse_obj(response.json()) == SelectRowsResponse(
    rows=TEST_DATA, total_num_rows=3)


def test_select_rows_with_cols_and_limit() -> None:
  url = f'/api/v1/datasets/{TEST_NAMESPACE}/{TEST_DATASET_NAME}/select_rows'
  options = SelectRowsOptions(
    columns=[('people', '*', 'zipcode'), ('people', '*', 'locations', '*', 'city')],
    limit=1,
    offset=1)
  response = client.post(url, json=options.dict())
  assert response.status_code == 200
  assert SelectRowsResponse.parse_obj(response.json()) == SelectRowsResponse(
    rows=[{
      'people.*.zipcode': [1, 2],
      'people.*.locations.*.city': [['city3', 'city4', 'city5'], ['city1']]
    }],
    total_num_rows=3)


def test_select_rows_with_cols_and_combine() -> None:
  url = f'/api/v1/datasets/{TEST_NAMESPACE}/{TEST_DATASET_NAME}/select_rows'
  options = SelectRowsOptions(
    columns=[('people', '*', 'zipcode'), ('people', '*', 'locations', '*', 'city')],
    combine_columns=True)
  response = client.post(url, json=options.dict())
  assert response.status_code == 200
  assert SelectRowsResponse.parse_obj(response.json()) == SelectRowsResponse(
    rows=[{
      'people': [{
        'zipcode': 0,
        'locations': [{
          'city': 'city1',
        }, {
          'city': 'city2',
        }]
      }]
    }, {
      'people': [{
        'zipcode': 1,
        'locations': [{
          'city': 'city3',
        }, {
          'city': 'city4'
        }, {
          'city': 'city5'
        }]
      }, {
        'zipcode': 2,
        'locations': [{
          'city': 'city1'
        }]
      }]
    }, {
      'people': None
    }],
    total_num_rows=3)


class LengthSignal(TextSignal):
  name = 'length_signal'

  def fields(self) -> Field:
    return field('int32')

  def compute(self, data: Iterable[RichData]) -> Iterable[Optional[Item]]:
    for text_content in data:
      yield len(text_content) if text_content is not None else None


def test_select_rows_star_plus_udf() -> None:
  url = f'/api/v1/datasets/{TEST_NAMESPACE}/{TEST_DATASET_NAME}/select_rows'
  udf = Column(path=('people', '*', 'name'), alias='len', signal_udf=LengthSignal())
  options = SelectRowsOptions(columns=['*', udf], combine_columns=True)
  response = client.post(url, json=options.dict())
  assert response.status_code == 200
  assert SelectRowsResponse.parse_obj(response.json()) == SelectRowsResponse(
    rows=[{
      'erased': False,
      'people': [{
        'name': enriched_item('A', {'length_signal': 1}),
        'zipcode': 0,
        'locations': [{
          'city': 'city1',
          'state': 'state1'
        }, {
          'city': 'city2',
          'state': 'state2'
        }]
      }]
    }, {
      'erased': True,
      'people': [{
        'name': enriched_item('B', {'length_signal': 1}),
        'zipcode': 1,
        'locations': [{
          'city': 'city3',
          'state': 'state3'
        }, {
          'city': 'city4'
        }, {
          'city': 'city5'
        }]
      }, {
        'name': enriched_item('C', {'length_signal': 1}),
        'zipcode': 2,
        'locations': [{
          'city': 'city1',
          'state': 'state1'
        }]
      }]
    }, {
      'erased': True
    }],
    total_num_rows=3)


def test_select_rows_schema_star_plus_udf() -> None:
  url = f'/api/v1/datasets/{TEST_NAMESPACE}/{TEST_DATASET_NAME}/select_rows_schema'
  signal = LengthSignal()
  udf = Column(path=('people', '*', 'name'), alias='len', signal_udf=signal)
  options = SelectRowsSchemaOptions(columns=['*', udf], combine_columns=True)
  response = client.post(url, json=options.dict())
  assert response.status_code == 200
  assert SelectRowsSchemaResult.parse_obj(response.json()) == SelectRowsSchemaResult(
    data_schema=schema({
      'erased': 'boolean',
      'people': [{
        'name': field(
          'string', fields={'length_signal': field('int32', signal.dict(exclude_none=True))}),
        'zipcode': 'int32',
        'locations': [{
          'city': 'string',
          'state': 'string'
        }]
      }]
    }),
    udfs=[SelectRowsSchemaUDF(path=('people', '*', 'name', 'length_signal'), alias='len')])


def test_select_rows_schema_no_cols() -> None:
  url = f'/api/v1/datasets/{TEST_NAMESPACE}/{TEST_DATASET_NAME}/select_rows_schema'
  options = SelectRowsSchemaOptions(combine_columns=True)
  response = client.post(url, json=options.dict())
  assert response.status_code == 200
  assert SelectRowsSchemaResult.parse_obj(response.json()) == SelectRowsSchemaResult(
    data_schema=schema({
      'erased': 'boolean',
      'people': [{
        'name': 'string',
        'zipcode': 'int32',
        'locations': [{
          'city': 'string',
          'state': 'string'
        }]
      }]
    }))


def test_compute_signal_auth(mocker: MockerFixture) -> None:
  mocker.patch.dict(os.environ, {'LILAC_AUTH_ENABLED': 'True'})

  url = f'/api/v1/datasets/{TEST_NAMESPACE}/{TEST_DATASET_NAME}/compute_signal'
  response = client.post(
    url, json=ComputeSignalOptions(signal=LengthSignal(), leaf_path=('people', 'name')).dict())
  assert response.status_code == 401
  assert response.is_error is True
  assert 'User does not have access to compute signals over this dataset.' in response.text


def test_delete_signal_auth(mocker: MockerFixture) -> None:
  mocker.patch.dict(os.environ, {'LILAC_AUTH_ENABLED': 'True'})

  url = f'/api/v1/datasets/{TEST_NAMESPACE}/{TEST_DATASET_NAME}/delete_signal'
  response = client.request(
    'DELETE', url, json=DeleteSignalOptions(signal_path=('doesnt', 'matter')).dict())
  assert response.status_code == 401
  assert response.is_error is True
  assert 'User does not have access to delete this signal.' in response.text


def test_update_settings_auth(mocker: MockerFixture) -> None:
  mocker.patch.dict(os.environ, {'LILAC_AUTH_ENABLED': 'True'})

  url = f'/api/v1/datasets/{TEST_NAMESPACE}/{TEST_DATASET_NAME}/settings'
  response = client.post(url, json=DatasetSettings().dict())
  assert response.status_code == 401
  assert response.is_error is True
  assert 'User does not have access to update the settings of this dataset.' in response.text
