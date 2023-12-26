"""Test our public dataset/signals computation REST API."""

import os
from typing import ClassVar, Iterable, Iterator, Optional

from fastapi.testclient import TestClient
from pytest_mock import MockerFixture

from .data.dataset_test_utils import TEST_DATASET_NAME, TEST_NAMESPACE
from .router_dataset_signals import ComputeSignalOptions, DeleteSignalOptions
from .schema import Field, Item, RichData, field
from .server import app
from .signal import TextSignal

client = TestClient(app)


class LengthSignal(TextSignal):
  name: ClassVar[str] = 'length_signal'

  def fields(self) -> Field:
    return field('int32')

  def compute(self, data: Iterable[RichData]) -> Iterator[Optional[Item]]:
    for text_content in data:
      yield len(text_content) if text_content is not None else None


def test_compute_signal_auth(mocker: MockerFixture) -> None:
  mocker.patch.dict(os.environ, {'LILAC_AUTH_ENABLED': 'True'})

  url = f'/api/v1/datasets/{TEST_NAMESPACE}/{TEST_DATASET_NAME}/compute_signal'
  response = client.post(
    url, json=ComputeSignalOptions(signal=LengthSignal(), leaf_path=('people', 'name')).model_dump()
  )
  assert response.status_code == 401
  assert response.is_error is True
  assert 'User does not have access to compute signals over this dataset.' in response.text


def test_delete_signal_auth(mocker: MockerFixture) -> None:
  mocker.patch.dict(os.environ, {'LILAC_AUTH_ENABLED': 'True'})

  url = f'/api/v1/datasets/{TEST_NAMESPACE}/{TEST_DATASET_NAME}/delete_signal'
  response = client.request(
    'DELETE', url, json=DeleteSignalOptions(signal_path=('doesnt', 'matter')).model_dump()
  )
  assert response.status_code == 401
  assert response.is_error is True
  assert 'User does not have access to delete this signal.' in response.text
