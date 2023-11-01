"""Test the public REST API for signals."""
import os
from pathlib import Path
from typing import ClassVar, Iterable, Optional

import pytest
from fastapi.testclient import TestClient
from pytest_mock import MockerFixture
from typing_extensions import override

from .router_signal import (
  SignalComputeOptions,
  SignalComputeResponse,
  SignalSchemaOptions,
  SignalSchemaResponse,
)
from .schema import Field, Item, RichData, SignalInputType, field
from .server import app
from .signal import Signal, clear_signal_registry, register_signal

client = TestClient(app)

EMBEDDINGS: list[tuple[str, list[float]]] = [
  ('hello', [1.0, 0.0, 0.0]),
  ('hello2', [1.0, 1.0, 0.0]),
  ('hello world', [1.0, 1.0, 1.0]),
  ('hello world2', [2.0, 1.0, 1.0]),
]

STR_EMBEDDINGS: dict[str, list[float]] = {text: embedding for text, embedding in EMBEDDINGS}


class TestQueryAndLengthSignal(Signal):
  """A test signal."""

  # Pydantic fields
  name: ClassVar[str] = 'test_signal'
  input_type: ClassVar[SignalInputType] = SignalInputType.TEXT

  query: str

  @override
  def fields(self) -> Field:
    return field('int32')

  @override
  def compute(self, data: Iterable[RichData]) -> Iterable[Optional[Item]]:
    return [f'{self.query}_{len(e)}' for e in data]


@pytest.fixture(scope='module', autouse=True)
def setup_teardown() -> Iterable[None]:
  # Setup.
  register_signal(TestQueryAndLengthSignal)
  # Unit test runs.
  yield
  # Teardown.
  clear_signal_registry()


@pytest.fixture(scope='function', autouse=True)
def setup_data_dir(tmp_path: Path, mocker: MockerFixture) -> None:
  mocker.patch.dict(os.environ, {'LILAC_PROJECT_DIR': str(tmp_path)})


def test_compute() -> None:
  # Compute the signal.
  url = '/api/v1/signals/compute'
  create_signal = SignalComputeOptions(
    signal=TestQueryAndLengthSignal(query='hi'), inputs=['hello', 'hello2']
  )
  response = client.post(url, json=create_signal.model_dump())
  assert response.status_code == 200
  assert SignalComputeResponse.model_validate(response.json()) == SignalComputeResponse(
    items=['hi_5', 'hi_6']
  )


def test_schema() -> None:
  # Get the schema for the signal.
  url = '/api/v1/signals/schema'
  signal = TestQueryAndLengthSignal(query='hi')
  create_signal = SignalSchemaOptions(signal=signal)
  response = client.post(url, json=create_signal.model_dump())
  assert response.status_code == 200
  assert SignalSchemaResponse.model_validate(response.json()) == SignalSchemaResponse(
    fields=signal.fields()
  )
