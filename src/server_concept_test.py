"""Test the public REST API for concepts."""
import uuid
from typing import Generator, Iterable, cast

import numpy as np
import pytest
from fastapi.testclient import TestClient
from pydantic import parse_obj_as
from pytest_mock import MockerFixture
from sklearn.linear_model import LogisticRegression
from typing_extensions import override

from .concepts.concept import Concept, ConceptModel, Example, ExampleIn, ExampleOrigin
from .concepts.db_concept import ConceptInfo, ConceptUpdate
from .config import CONFIG
from .router_concept import ConceptModelResponse, ScoreBody, ScoreExample, ScoreResponse
from .schema import RichData, SignalInputType, SignalOut
from .server import app
from .signals.signal import TextEmbeddingSignal, clear_signal_registry, register_signal

client = TestClient(app)

EMBEDDINGS: list[tuple[str, list[float]]] = [('hello', [1.0, 0.0, 0.0]), ('hello2', [1.0, 1.0,
                                                                                     0.0]),
                                             ('hello world', [1.0, 1.0, 1.0]),
                                             ('hello world2', [2.0, 1.0, 1.0])]

STR_EMBEDDINGS: dict[str, list[float]] = {text: embedding for text, embedding in EMBEDDINGS}


class TestEmbedding(TextEmbeddingSignal):
  """A test embed function."""
  name = 'test_embedding'

  @override
  def compute(self, data: Iterable[RichData]) -> Iterable[SignalOut]:
    """Call the embedding function."""
    embeddings = [np.array(STR_EMBEDDINGS[cast(str, example)]) for example in data]
    yield from embeddings


@pytest.fixture(scope='module', autouse=True)
def setup_teardown() -> Iterable[None]:
  # Setup.
  register_signal(TestEmbedding)
  # Unit test runs.
  yield
  # Teardown.
  clear_signal_registry()


@pytest.fixture(autouse=True)
def test_data(tmp_path_factory: pytest.TempPathFactory) -> Generator:
  data_path = CONFIG['LILAC_DATA_PATH']
  tmp_path = tmp_path_factory.mktemp('data')
  CONFIG['LILAC_DATA_PATH'] = str(tmp_path)

  yield

  # Teardown.
  CONFIG['LILAC_DATA_PATH'] = data_path or ''


def _uuid(id: bytes) -> uuid.UUID:
  return uuid.UUID((id * 16).hex())


def test_concept_edits(mocker: MockerFixture) -> None:
  mock_uuid = mocker.patch.object(uuid, 'uuid4', autospec=True)

  url = '/api/v1/concepts/'
  response = client.get(url)

  assert response.status_code == 200
  assert response.json() == []

  # Make sure we can create a concept with an example.
  mock_uuid.return_value = _uuid(b'1')
  url = '/api/v1/concepts/concept_namespace/concept'
  concept_update = ConceptUpdate(insert=[
    ExampleIn(
      label=True,
      text='hello',
      origin=ExampleOrigin(
        dataset_namespace='dataset_namespace', dataset_name='dataset', dataset_row_id='d1'))
  ])
  response = client.post(url, json=concept_update.dict())
  assert response.status_code == 200
  assert Concept.parse_obj(response.json()) == Concept(
    namespace='concept_namespace',
    concept_name='concept',
    type='text',
    data={
      _uuid(b'1').hex: Example(
        id=_uuid(b'1').hex,
        label=True,
        text='hello',
        origin=ExampleOrigin(
          dataset_namespace='dataset_namespace', dataset_name='dataset', dataset_row_id='d1'))
    },
    version=1)

  url = '/api/v1/concepts/'
  response = client.get(url)

  assert response.status_code == 200
  assert parse_obj_as(list[ConceptInfo], response.json()) == [
    ConceptInfo(namespace='concept_namespace', name='concept', input_type=SignalInputType.TEXT)
  ]

  # Add another example.
  mock_uuid.return_value = _uuid(b'2')
  url = '/api/v1/concepts/concept_namespace/concept'
  concept_update = ConceptUpdate(insert=[
    ExampleIn(
      label=True,
      text='hello2',
      origin=ExampleOrigin(
        dataset_namespace='dataset_namespace', dataset_name='dataset', dataset_row_id='d2'))
  ])
  response = client.post(url, json=concept_update.dict())
  assert response.status_code == 200
  assert Concept.parse_obj(response.json()) == Concept(
    namespace='concept_namespace',
    concept_name='concept',
    type='text',
    data={
      _uuid(b'1').hex: Example(
        id=_uuid(b'1').hex,
        label=True,
        text='hello',
        origin=ExampleOrigin(
          dataset_namespace='dataset_namespace', dataset_name='dataset', dataset_row_id='d1')),
      _uuid(b'2').hex: Example(
        id=_uuid(b'2').hex,
        label=True,
        text='hello2',
        origin=ExampleOrigin(
          dataset_namespace='dataset_namespace', dataset_name='dataset', dataset_row_id='d2'))
    },
    version=2)

  # Edit both examples.
  url = '/api/v1/concepts/concept_namespace/concept'
  concept_update = ConceptUpdate(update=[
    # Switch the label.
    Example(id=_uuid(b'1').hex, label=False, text='hello'),
    # Switch the text.
    Example(id=_uuid(b'2').hex, label=True, text='hello world'),
  ])
  response = client.post(url, json=concept_update.dict())
  assert response.status_code == 200
  assert Concept.parse_obj(response.json()) == Concept(
    namespace='concept_namespace',
    concept_name='concept',
    type='text',
    data={
      _uuid(b'1').hex: Example(id=_uuid(b'1').hex, label=False, text='hello'),
      _uuid(b'2').hex: Example(id=_uuid(b'2').hex, label=True, text='hello world')
    },
    version=3)

  # Delete the first example.
  url = '/api/v1/concepts/concept_namespace/concept'
  concept_update = ConceptUpdate(remove=[_uuid(b'1').hex])
  response = client.post(url, json=concept_update.dict())
  assert response.status_code == 200
  assert Concept.parse_obj(response.json()) == Concept(
    namespace='concept_namespace',
    concept_name='concept',
    type='text',
    data={_uuid(b'2').hex: Example(id=_uuid(b'2').hex, label=True, text='hello world')},
    version=4)

  # The concept still exists.
  url = '/api/v1/concepts/'
  response = client.get(url)

  assert response.status_code == 200
  assert parse_obj_as(list[ConceptInfo], response.json()) == [
    ConceptInfo(namespace='concept_namespace', name='concept', input_type=SignalInputType.TEXT)
  ]


def test_concept_model_sync(mocker: MockerFixture) -> None:
  mock_uuid = mocker.patch.object(uuid, 'uuid4', autospec=True)

  url = '/api/v1/concepts/'
  response = client.get(url)

  assert response.status_code == 200
  assert response.json() == []

  # Add two examples.
  mock_uuid.side_effect = [_uuid(b'1'), _uuid(b'2')]
  url = '/api/v1/concepts/concept_namespace/concept'
  concept_update = ConceptUpdate(insert=[
    ExampleIn(
      label=True,
      text='hello',
      origin=ExampleOrigin(
        dataset_namespace='dataset_namespace', dataset_name='dataset', dataset_row_id='d1')),
    ExampleIn(
      label=False,
      text='hello world',
      origin=ExampleOrigin(
        dataset_namespace='dataset_namespace', dataset_name='dataset', dataset_row_id='d2'))
  ])
  response = client.post(url, json=concept_update.dict())
  assert response.status_code == 200

  # Get the concept model.
  url = '/api/v1/concepts/concept_namespace/concept/test_embedding?sync_model=False'
  response = client.get(url)
  assert response.status_code == 200
  assert ConceptModelResponse.parse_obj(response.json()) == ConceptModelResponse(
    model=ConceptModel(
      namespace='concept_namespace',
      concept_name='concept',
      embedding_name='test_embedding',
      version=-1),
    # The model shouldn't yet be synced because we set sync_model=False.
    model_synced=False)

  # Sync the concept model.
  url = '/api/v1/concepts/concept_namespace/concept/test_embedding?sync_model=True'
  response = client.get(url)
  assert response.status_code == 200
  assert ConceptModelResponse.parse_obj(response.json()) == ConceptModelResponse(
    model=ConceptModel(
      namespace='concept_namespace',
      concept_name='concept',
      embedding_name='test_embedding',
      version=1),
    # The model should be synced because we set sync_model=True.
    model_synced=True)

  # Score an example.
  mock_predict_proba = mocker.patch.object(LogisticRegression, 'predict_proba', autospec=True)
  mock_predict_proba.return_value = np.array([[0.1, 0.9], [0.0, 1.0]])
  url = '/api/v1/concepts/concept_namespace/concept/test_embedding/score'
  score_body = ScoreBody(examples=[ScoreExample(text='hello world'), ScoreExample(text='hello')])
  response = client.post(url, json=score_body.dict())
  assert response.status_code == 200
  assert ScoreResponse.parse_obj(response.json()) == ScoreResponse(
    scores=[0.9, 1.0],
    # The model should already be synced.
    model_synced=False)
