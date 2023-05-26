"""Test the public REST API for concepts."""
import uuid
from pathlib import Path
from typing import Iterable, cast

import numpy as np
import pytest
from fastapi.testclient import TestClient
from pydantic import parse_obj_as
from pytest_mock import MockerFixture
from typing_extensions import override

from .concepts.concept import DRAFT_MAIN, Concept, ConceptModel, Example, ExampleIn, ExampleOrigin
from .concepts.db_concept import ConceptInfo, ConceptUpdate
from .config import CONFIG
from .data.dataset_test_utils import TEST_DATASET_NAME, TEST_NAMESPACE, TestDataMaker
from .router_concept import (
  ConceptDatasetOptions,
  ConceptModelResponse,
  CreateConceptOptions,
  MergeConceptDraftOptions,
  ScoreBody,
  ScoreExample,
  ScoreResponse,
)
from .schema import UUID_COLUMN, RichData, SignalInputType, SignalOut
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


@pytest.fixture(scope='function', autouse=True)
def setup_data_dir(tmp_path: Path, mocker: MockerFixture) -> None:
  mocker.patch.dict(CONFIG, {'LILAC_DATA_PATH': str(tmp_path)})


def _uuid(id: bytes) -> uuid.UUID:
  return uuid.UUID((id * 16).hex())


def test_concept_create() -> None:
  url = '/api/v1/concepts/'
  response = client.get(url)

  assert response.status_code == 200
  assert response.json() == []

  # Create a concept.
  url = '/api/v1/concepts/create'
  create_concept = CreateConceptOptions(
    namespace='concept_namespace', name='concept', type=SignalInputType.TEXT)
  response = client.post(url, json=create_concept.dict())
  assert response.status_code == 200
  assert response.json() == Concept(
    namespace='concept_namespace',
    concept_name='concept',
    type=SignalInputType.TEXT,
    data={},
    version=0).dict()

  # Make sure list shows us the new concept.
  url = '/api/v1/concepts/'
  response = client.get(url)
  assert response.status_code == 200
  assert parse_obj_as(list[ConceptInfo], response.json()) == [
    ConceptInfo(
      namespace='concept_namespace', name='concept', type=SignalInputType.TEXT, drafts=[DRAFT_MAIN])
  ]


def test_concept_create_negative_examples(make_test_data: TestDataMaker) -> None:
  url = '/api/v1/concepts/'
  response = client.get(url)

  assert response.status_code == 200
  assert response.json() == []

  make_test_data([
    {
      UUID_COLUMN: '1',
      'body': 'hello. world'
    },
    {
      UUID_COLUMN: '2',
      'body': 'How is everybody?'
    },
  ])

  # Create a concept.
  url = '/api/v1/concepts/create'

  # Provide dataset options for negative examples.
  dataset_options = ConceptDatasetOptions(
    namespace=TEST_NAMESPACE, name=TEST_DATASET_NAME, path='body')

  create_concept = CreateConceptOptions(
    namespace='concept_namespace',
    name='concept',
    type=SignalInputType.TEXT,
    dataset=dataset_options)

  response = client.post(url, json=create_concept.dict())
  assert response.status_code == 200

  # Make sure the concept has the correct negative examples.
  concept = Concept.parse_obj(response.json())
  negative_examples = set([ex.text for ex in concept.data.values()])
  expected_negative_examples = set(['hello.', 'world', 'How is everybody?'])
  assert negative_examples == expected_negative_examples

  # Make sure list shows us the new concept.
  url = '/api/v1/concepts/'
  response = client.get(url)
  assert response.status_code == 200
  assert parse_obj_as(list[ConceptInfo], response.json()) == [
    ConceptInfo(
      namespace='concept_namespace', name='concept', type=SignalInputType.TEXT, drafts=[DRAFT_MAIN])
  ]


def test_concept_edits(mocker: MockerFixture) -> None:
  mock_uuid = mocker.patch.object(uuid, 'uuid4', autospec=True)

  # Create the concept.
  response = client.post(
    '/api/v1/concepts/create',
    json=CreateConceptOptions(
      namespace='concept_namespace', name='concept', type=SignalInputType.TEXT).dict())

  # Make sure we can add an example.
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
    ConceptInfo(
      namespace='concept_namespace', name='concept', type=SignalInputType.TEXT, drafts=[DRAFT_MAIN])
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
    ConceptInfo(
      namespace='concept_namespace', name='concept', type=SignalInputType.TEXT, drafts=[DRAFT_MAIN])
  ]


def test_concept_drafts(mocker: MockerFixture) -> None:
  mock_uuid = mocker.patch.object(uuid, 'uuid4', autospec=True)

  # Create the concept.
  response = client.post(
    '/api/v1/concepts/create',
    json=CreateConceptOptions(
      namespace='concept_namespace', name='concept', type=SignalInputType.TEXT).dict())

  # Add examples, some drafts.
  mock_uuid.side_effect = [_uuid(b'1'), _uuid(b'2'), _uuid(b'3'), _uuid(b'4')]
  url = '/api/v1/concepts/concept_namespace/concept'
  concept_update = ConceptUpdate(insert=[
    ExampleIn(label=True, text='in concept'),
    ExampleIn(label=False, text='out of concept'),
    ExampleIn(label=False, text='in concept', draft='test_draft'),
    ExampleIn(label=False, text='out of concept draft', draft='test_draft')
  ])
  response = client.post(url, json=concept_update.dict())
  assert response.status_code == 200

  # Make sure list shows us the drafts
  url = '/api/v1/concepts/'
  response = client.get(url)
  assert response.status_code == 200
  assert parse_obj_as(list[ConceptInfo], response.json()) == [
    ConceptInfo(
      namespace='concept_namespace',
      name='concept',
      type=SignalInputType.TEXT,
      drafts=[DRAFT_MAIN, 'test_draft'])
  ]

  # Make sure when we request main, we only get data in main.
  url = '/api/v1/concepts/concept_namespace/concept'
  response = client.get(url)
  assert response.status_code == 200
  assert Concept.parse_obj(response.json()) == Concept(
    namespace='concept_namespace',
    concept_name='concept',
    type='text',
    data={
      # Only main are returned.
      _uuid(b'1').hex: Example(id=_uuid(b'1').hex, label=True, text='in concept'),
      _uuid(b'2').hex: Example(id=_uuid(b'2').hex, label=False, text='out of concept')
    },
    version=1)

  # Make sure when we request the draft, we get the draft data deduped with main.
  url = '/api/v1/concepts/concept_namespace/concept?draft=test_draft'
  response = client.get(url)
  assert response.status_code == 200
  assert Concept.parse_obj(response.json()) == Concept(
    namespace='concept_namespace',
    concept_name='concept',
    type='text',
    data={
      # b'1' is deduped with b'3'.
      _uuid(b'2').hex: Example(id=_uuid(b'2').hex, label=False, text='out of concept'),
      # ID 3 is a duplicate of main's 1.
      _uuid(b'3').hex: Example(
        id=_uuid(b'3').hex, label=False, text='in concept', draft='test_draft'),
      _uuid(b'4').hex: Example(
        id=_uuid(b'4').hex, label=False, text='out of concept draft', draft='test_draft')
    },
    version=1)

  # Merge the draft.
  response = client.post(
    '/api/v1/concepts/concept_namespace/concept/merge_draft',
    json=MergeConceptDraftOptions(draft='test_draft').dict())
  assert response.status_code == 200

  # Make sure we get the merged drafts.
  url = '/api/v1/concepts/concept_namespace/concept'
  response = client.get(url)
  assert response.status_code == 200
  assert Concept.parse_obj(response.json()).dict() == Concept(
    namespace='concept_namespace',
    concept_name='concept',
    type='text',
    data={
      # b'1' is deduped with b'3'.
      _uuid(b'2').hex: Example(id=_uuid(b'2').hex, label=False, text='out of concept'),
      # ID 3 is a duplicate of main's 1.
      _uuid(b'3').hex: Example(id=_uuid(b'3').hex, label=False, text='in concept'),
      _uuid(b'4').hex: Example(id=_uuid(b'4').hex, label=False, text='out of concept draft')
    },
    version=2).dict()


def test_concept_model_sync(mocker: MockerFixture) -> None:
  mock_uuid = mocker.patch.object(uuid, 'uuid4', autospec=True)

  # Create the concept.
  response = client.post(
    '/api/v1/concepts/create',
    json=CreateConceptOptions(
      namespace='concept_namespace', name='concept', type=SignalInputType.TEXT).dict())

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
  mock_score_emb = mocker.patch.object(ConceptModel, 'score_embeddings', autospec=True)
  mock_score_emb.return_value = np.array([0.9, 1.0])
  url = '/api/v1/concepts/concept_namespace/concept/test_embedding/score'
  score_body = ScoreBody(examples=[ScoreExample(text='hello world'), ScoreExample(text='hello')])
  response = client.post(url, json=score_body.dict())
  assert response.status_code == 200
  assert ScoreResponse.parse_obj(response.json()) == ScoreResponse(
    scores=[0.9, 1.0],
    # The model should already be synced.
    model_synced=False)


def test_concept_edits_error_before_create(mocker: MockerFixture) -> None:
  url = '/api/v1/concepts/concept_namespace/concept'
  concept_update = ConceptUpdate(insert=[
    ExampleIn(
      label=True,
      text='hello',
      origin=ExampleOrigin(
        dataset_namespace='dataset_namespace', dataset_name='dataset', dataset_row_id='d1'))
  ])
  response = client.post(url, json=concept_update.dict())
  assert response.is_error is True
  assert response.status_code == 500


def test_concept_edits_wrong_type(mocker: MockerFixture) -> None:
  # Create the concept.
  response = client.post(
    '/api/v1/concepts/create',
    json=CreateConceptOptions(
      namespace='concept_namespace', name='concept', type=SignalInputType.IMAGE).dict())

  url = '/api/v1/concepts/concept_namespace/concept'
  concept_update = ConceptUpdate(insert=[
    ExampleIn(
      label=True,
      text='hello',
      origin=ExampleOrigin(
        dataset_namespace='dataset_namespace', dataset_name='dataset', dataset_row_id='d1'))
  ])
  response = client.post(url, json=concept_update.dict())
  assert response.is_error is True
  assert response.status_code == 500
