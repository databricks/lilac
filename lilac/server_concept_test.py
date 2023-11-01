"""Test the public REST API for concepts."""
import os
import uuid
from pathlib import Path
from typing import ClassVar, Iterable, cast

import numpy as np
import pytest
from fastapi.testclient import TestClient
from pydantic import TypeAdapter
from pytest_mock import MockerFixture
from typing_extensions import override

from .concepts.concept import (
  DRAFT_MAIN,
  Concept,
  ConceptMetadata,
  ConceptModel,
  ConceptType,
  Example,
  ExampleIn,
  ExampleOrigin,
)
from .concepts.db_concept import ConceptACL, ConceptInfo, ConceptUpdate
from .router_concept import (
  ConceptModelInfo,
  CreateConceptOptions,
  MergeConceptDraftOptions,
  ScoreBody,
  ScoreExample,
)
from .schema import Item, RichData, lilac_embedding, lilac_span
from .server import app
from .signal import TextEmbeddingSignal, clear_signal_registry, register_signal
from .test_utils import fake_uuid

client = TestClient(app)

EMBEDDINGS: list[tuple[str, list[float]]] = [
  ('hello', [1.0, 0.0, 0.0]),
  ('hello2', [1.0, 1.0, 0.0]),
  ('hello world', [1.0, 1.0, 1.0]),
  ('hello world2', [2.0, 1.0, 1.0]),
]

STR_EMBEDDINGS: dict[str, list[float]] = {text: embedding for text, embedding in EMBEDDINGS}


class TestEmbedding(TextEmbeddingSignal):
  """A test embed function."""

  name: ClassVar[str] = 'test_embedding'

  @override
  def compute(self, data: Iterable[RichData]) -> Iterable[Item]:
    """Call the embedding function."""
    for example in data:
      yield [lilac_embedding(0, len(example), np.array(STR_EMBEDDINGS[cast(str, example)]))]


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
  mocker.patch.dict(os.environ, {'LILAC_PROJECT_DIR': str(tmp_path)})


def _remove_lilac_concepts(concepts: list[ConceptInfo]) -> list[ConceptInfo]:
  return list(filter(lambda c: c.namespace != 'lilac', concepts))


def test_list_lilac_concepts() -> None:
  url = '/api/v1/concepts/'
  response = client.get(url)

  assert response.status_code == 200
  # Make sure lilac concepts exist.
  assert filter(
    lambda c: c.concept_name == 'positive-sentiment' and c.namespace == 'lilac', response.json()
  )


def test_concept_create() -> None:
  url = '/api/v1/concepts/'
  response = client.get(url)

  assert response.status_code == 200
  adapter = TypeAdapter(list[ConceptInfo])
  response_concepts = _remove_lilac_concepts(adapter.validate_python(response.json()))
  assert response_concepts == []

  # Create a concept.
  url = '/api/v1/concepts/create'
  create_concept = CreateConceptOptions(
    namespace='concept_namespace',
    name='concept',
    type=ConceptType.TEXT,
    metadata=ConceptMetadata(is_public=False, tags=['test_tag'], description='test_description'),
  )
  response = client.post(url, json=create_concept.model_dump())
  assert response.status_code == 200
  assert Concept.model_validate(response.json()) == Concept(
    namespace='concept_namespace',
    concept_name='concept',
    type=ConceptType.TEXT,
    data={},
    version=0,
    metadata=ConceptMetadata(is_public=False, tags=['test_tag'], description='test_description'),
  )

  # Make sure list shows us the new concept.
  url = '/api/v1/concepts/'
  response = client.get(url)
  assert response.status_code == 200
  response_concepts = _remove_lilac_concepts(adapter.validate_python(response.json()))
  assert response_concepts == [
    ConceptInfo(
      namespace='concept_namespace',
      name='concept',
      type=ConceptType.TEXT,
      drafts=[DRAFT_MAIN],
      acls=ConceptACL(read=True, write=True),
      metadata=ConceptMetadata(is_public=False, tags=['test_tag'], description='test_description'),
    )
  ]


def test_concept_update_metadata() -> None:
  url = '/api/v1/concepts/'
  response = client.get(url)
  adapter = TypeAdapter(list[ConceptInfo])

  assert response.status_code == 200
  response_concepts = _remove_lilac_concepts(adapter.validate_python(response.json()))
  assert response_concepts == []

  # Create a concept.
  url = '/api/v1/concepts/create'
  create_concept = CreateConceptOptions(
    namespace='concept_namespace', name='concept', type=ConceptType.TEXT
  )
  response = client.post(url, json=create_concept.model_dump())
  assert response.status_code == 200

  # Update the metadata.
  url = '/api/v1/concepts/concept_namespace/concept/metadata'
  update_metadata = ConceptMetadata(
    is_public=True, tags=['test_tag'], description='test_description'
  )
  response = client.post(url, json=update_metadata.model_dump())
  assert response.status_code == 200

  # Make sure list shows us the new concept.
  url = '/api/v1/concepts/'
  response = client.get(url)
  assert response.status_code == 200
  response_concepts = _remove_lilac_concepts(adapter.validate_python(response.json()))
  assert response_concepts == [
    ConceptInfo(
      namespace='concept_namespace',
      name='concept',
      type=ConceptType.TEXT,
      drafts=[DRAFT_MAIN],
      acls=ConceptACL(read=True, write=True),
      metadata=ConceptMetadata(is_public=True, tags=['test_tag'], description='test_description'),
    )
  ]


def test_concept_delete() -> None:
  # Create a concept.
  client.post(
    '/api/v1/concepts/create',
    json=CreateConceptOptions(
      namespace='concept_namespace', name='concept', type=ConceptType.TEXT
    ).model_dump(),
  )

  adapter = TypeAdapter(list[ConceptInfo])
  response = client.get('/api/v1/concepts/')
  response_concepts = _remove_lilac_concepts(adapter.validate_python(response.json()))
  assert len(response_concepts) == 1

  # Delete the concept.
  url = '/api/v1/concepts/concept_namespace/concept'
  response = client.delete(url)
  assert response.status_code == 200

  # Make sure list shows no concepts.
  response = client.get('/api/v1/concepts/')
  response_concepts = _remove_lilac_concepts(adapter.validate_python(response.json()))
  assert response_concepts == []


def test_concept_edits(mocker: MockerFixture) -> None:
  mock_uuid = mocker.patch.object(uuid, 'uuid4', autospec=True)
  adapter = TypeAdapter(list[ConceptInfo])

  # Create the concept.
  response = client.post(
    '/api/v1/concepts/create',
    json=CreateConceptOptions(
      namespace='concept_namespace', name='concept', type=ConceptType.TEXT
    ).model_dump(),
  )

  # Make sure we can add an example.
  mock_uuid.return_value = fake_uuid(b'1')
  url = '/api/v1/concepts/concept_namespace/concept'
  concept_update = ConceptUpdate(
    insert=[
      ExampleIn(
        label=True,
        text='hello',
        origin=ExampleOrigin(
          dataset_namespace='dataset_namespace', dataset_name='dataset', dataset_row_id='d1'
        ),
      )
    ]
  )
  response = client.post(url, json=concept_update.model_dump())
  assert response.status_code == 200
  assert Concept.model_validate(response.json()) == Concept(
    namespace='concept_namespace',
    concept_name='concept',
    type=ConceptType.TEXT,
    data={
      fake_uuid(b'1').hex: Example(
        id=fake_uuid(b'1').hex,
        label=True,
        text='hello',
        origin=ExampleOrigin(
          dataset_namespace='dataset_namespace', dataset_name='dataset', dataset_row_id='d1'
        ),
      )
    },
    version=1,
  )

  url = '/api/v1/concepts/'
  response = client.get(url)

  assert response.status_code == 200
  response_concepts = _remove_lilac_concepts(adapter.validate_python(response.json()))
  assert response_concepts == [
    ConceptInfo(
      namespace='concept_namespace',
      name='concept',
      type=ConceptType.TEXT,
      drafts=[DRAFT_MAIN],
      acls=ConceptACL(read=True, write=True),
      metadata=ConceptMetadata(),
    )
  ]

  # Add another example.
  mock_uuid.return_value = fake_uuid(b'2')
  url = '/api/v1/concepts/concept_namespace/concept'
  concept_update = ConceptUpdate(
    insert=[
      ExampleIn(
        label=True,
        text='hello2',
        origin=ExampleOrigin(
          dataset_namespace='dataset_namespace', dataset_name='dataset', dataset_row_id='d2'
        ),
      )
    ]
  )
  response = client.post(url, json=concept_update.model_dump())
  assert response.status_code == 200
  assert Concept.model_validate(response.json()) == Concept(
    namespace='concept_namespace',
    concept_name='concept',
    type=ConceptType.TEXT,
    data={
      fake_uuid(b'1').hex: Example(
        id=fake_uuid(b'1').hex,
        label=True,
        text='hello',
        origin=ExampleOrigin(
          dataset_namespace='dataset_namespace', dataset_name='dataset', dataset_row_id='d1'
        ),
      ),
      fake_uuid(b'2').hex: Example(
        id=fake_uuid(b'2').hex,
        label=True,
        text='hello2',
        origin=ExampleOrigin(
          dataset_namespace='dataset_namespace', dataset_name='dataset', dataset_row_id='d2'
        ),
      ),
    },
    version=2,
  )

  # Edit both examples.
  url = '/api/v1/concepts/concept_namespace/concept'
  concept_update = ConceptUpdate(
    update=[
      # Switch the label.
      Example(id=fake_uuid(b'1').hex, label=False, text='hello'),
      # Switch the text.
      Example(id=fake_uuid(b'2').hex, label=True, text='hello world'),
    ]
  )
  response = client.post(url, json=concept_update.model_dump())
  assert response.status_code == 200
  assert Concept.model_validate(response.json()) == Concept(
    namespace='concept_namespace',
    concept_name='concept',
    type=ConceptType.TEXT,
    data={
      fake_uuid(b'1').hex: Example(id=fake_uuid(b'1').hex, label=False, text='hello'),
      fake_uuid(b'2').hex: Example(id=fake_uuid(b'2').hex, label=True, text='hello world'),
    },
    version=3,
  )

  # Delete the first example.
  url = '/api/v1/concepts/concept_namespace/concept'
  concept_update = ConceptUpdate(remove=[fake_uuid(b'1').hex])
  response = client.post(url, json=concept_update.model_dump())
  assert response.status_code == 200
  assert Concept.model_validate(response.json()) == Concept(
    namespace='concept_namespace',
    concept_name='concept',
    type=ConceptType.TEXT,
    data={fake_uuid(b'2').hex: Example(id=fake_uuid(b'2').hex, label=True, text='hello world')},
    version=4,
  )

  # The concept still exists.
  url = '/api/v1/concepts/'
  response = client.get(url)

  assert response.status_code == 200
  response_concepts = _remove_lilac_concepts(adapter.validate_python(response.json()))
  assert response_concepts == [
    ConceptInfo(
      namespace='concept_namespace',
      name='concept',
      type=ConceptType.TEXT,
      drafts=[DRAFT_MAIN],
      acls=ConceptACL(read=True, write=True),
      metadata=ConceptMetadata(),
    )
  ]


def test_concept_drafts(mocker: MockerFixture) -> None:
  mock_uuid = mocker.patch.object(uuid, 'uuid4', autospec=True)

  # Create the concept.
  response = client.post(
    '/api/v1/concepts/create',
    json=CreateConceptOptions(
      namespace='concept_namespace', name='concept', type=ConceptType.TEXT
    ).model_dump(),
  )

  # Add examples, some drafts.
  mock_uuid.side_effect = [fake_uuid(b'1'), fake_uuid(b'2'), fake_uuid(b'3'), fake_uuid(b'4')]
  url = '/api/v1/concepts/concept_namespace/concept'
  concept_update = ConceptUpdate(
    insert=[
      ExampleIn(label=True, text='in concept'),
      ExampleIn(label=False, text='out of concept'),
      ExampleIn(label=False, text='in concept', draft='test_draft'),
      ExampleIn(label=False, text='out of concept draft', draft='test_draft'),
    ]
  )
  response = client.post(url, json=concept_update.model_dump())
  assert response.status_code == 200

  # Make sure list shows us the drafts
  url = '/api/v1/concepts/'
  response = client.get(url)
  assert response.status_code == 200
  # Remove lilac concepts for the test.
  adapter = TypeAdapter(list[ConceptInfo])
  concepts = list(
    filter(lambda c: c.namespace != 'lilac', adapter.validate_python(response.json()))
  )

  assert concepts == [
    ConceptInfo(
      namespace='concept_namespace',
      name='concept',
      type=ConceptType.TEXT,
      drafts=[DRAFT_MAIN, 'test_draft'],
      acls=ConceptACL(read=True, write=True),
      metadata=ConceptMetadata(),
    )
  ]

  # Make sure when we request main, we only get data in main.
  url = '/api/v1/concepts/concept_namespace/concept'
  response = client.get(url)
  assert response.status_code == 200
  assert Concept.model_validate(response.json()) == Concept(
    namespace='concept_namespace',
    concept_name='concept',
    type=ConceptType.TEXT,
    data={
      # Only main are returned.
      fake_uuid(b'1').hex: Example(id=fake_uuid(b'1').hex, label=True, text='in concept'),
      fake_uuid(b'2').hex: Example(id=fake_uuid(b'2').hex, label=False, text='out of concept'),
    },
    version=1,
  )

  # Make sure when we request the draft, we get the draft data deduped with main.
  url = '/api/v1/concepts/concept_namespace/concept?draft=test_draft'
  response = client.get(url)
  assert response.status_code == 200
  assert Concept.model_validate(response.json()) == Concept(
    namespace='concept_namespace',
    concept_name='concept',
    type=ConceptType.TEXT,
    data={
      # b'1' is deduped with b'3'.
      fake_uuid(b'2').hex: Example(id=fake_uuid(b'2').hex, label=False, text='out of concept'),
      # ID 3 is a duplicate of main's 1.
      fake_uuid(b'3').hex: Example(
        id=fake_uuid(b'3').hex, label=False, text='in concept', draft='test_draft'
      ),
      fake_uuid(b'4').hex: Example(
        id=fake_uuid(b'4').hex, label=False, text='out of concept draft', draft='test_draft'
      ),
    },
    version=1,
  )

  # Merge the draft.
  response = client.post(
    '/api/v1/concepts/concept_namespace/concept/merge_draft',
    json=MergeConceptDraftOptions(draft='test_draft').model_dump(),
  )
  assert response.status_code == 200

  # Make sure we get the merged drafts.
  url = '/api/v1/concepts/concept_namespace/concept'
  response = client.get(url)
  assert response.status_code == 200
  assert (
    Concept.model_validate(response.json()).model_dump()
    == Concept(
      namespace='concept_namespace',
      concept_name='concept',
      type=ConceptType.TEXT,
      data={
        # b'1' is deduped with b'3'.
        fake_uuid(b'2').hex: Example(id=fake_uuid(b'2').hex, label=False, text='out of concept'),
        # ID 3 is a duplicate of main's 1.
        fake_uuid(b'3').hex: Example(id=fake_uuid(b'3').hex, label=False, text='in concept'),
        fake_uuid(b'4').hex: Example(
          id=fake_uuid(b'4').hex, label=False, text='out of concept draft'
        ),
      },
      version=2,
    ).model_dump()
  )


def test_concept_model_sync(mocker: MockerFixture) -> None:
  mock_uuid = mocker.patch.object(uuid, 'uuid4', autospec=True)

  # Create the concept.
  response = client.post(
    '/api/v1/concepts/create',
    json=CreateConceptOptions(
      namespace='concept_namespace', name='concept', type=ConceptType.TEXT
    ).model_dump(),
  )

  # Add two examples.
  mock_uuid.side_effect = [fake_uuid(b'1'), fake_uuid(b'2')]
  url = '/api/v1/concepts/concept_namespace/concept'
  concept_update = ConceptUpdate(
    insert=[
      ExampleIn(
        label=True,
        text='hello',
        origin=ExampleOrigin(
          dataset_namespace='dataset_namespace', dataset_name='dataset', dataset_row_id='d1'
        ),
      ),
      ExampleIn(
        label=False,
        text='hello world',
        origin=ExampleOrigin(
          dataset_namespace='dataset_namespace', dataset_name='dataset', dataset_row_id='d2'
        ),
      ),
    ]
  )
  response = client.post(url, json=concept_update.model_dump())
  assert response.status_code == 200

  # Get the concept model, without creating it.
  url = '/api/v1/concepts/concept_namespace/concept/model/test_embedding'
  response = client.get(url, params={'create_if_not_exists': False})
  assert response.status_code == 200
  assert response.json() is None

  # Get the concept model, and create it.
  url = '/api/v1/concepts/concept_namespace/concept/model/test_embedding'
  response = client.get(url, params={'create_if_not_exists': True})
  assert response.status_code == 200
  assert ConceptModelInfo.model_validate(response.json()) == ConceptModelInfo(
    namespace='concept_namespace',
    concept_name='concept',
    embedding_name='test_embedding',
    version=1,
  )

  # Score an example.
  mock_score_emb = mocker.patch.object(ConceptModel, 'score_embeddings', autospec=True)
  # The return value here is a batch of values.
  mock_score_emb.return_value = np.array([0.9, 1.0])
  url = '/api/v1/concepts/concept_namespace/concept/model/test_embedding/score'
  score_body = ScoreBody(examples=[ScoreExample(text='hello world'), ScoreExample(text='hello')])
  response = client.post(url, json=score_body.model_dump())
  assert response.status_code == 200
  assert response.json() == [
    [lilac_span(0, 11, {'score': 0.9})],
    [lilac_span(0, 5, {'score': 1.0})],
  ]


def test_concept_edits_error_before_create(mocker: MockerFixture) -> None:
  url = '/api/v1/concepts/concept_namespace/concept'
  concept_update = ConceptUpdate(
    insert=[
      ExampleIn(
        label=True,
        text='hello',
        origin=ExampleOrigin(
          dataset_namespace='dataset_namespace', dataset_name='dataset', dataset_row_id='d1'
        ),
      )
    ]
  )
  response = client.post(url, json=concept_update.model_dump())
  assert response.is_error is True
  assert response.status_code == 500


def test_concept_edits_wrong_type(mocker: MockerFixture) -> None:
  # Create the concept.
  response = client.post(
    '/api/v1/concepts/create',
    json=CreateConceptOptions(
      namespace='concept_namespace', name='concept', type=ConceptType.IMAGE
    ).model_dump(),
  )

  url = '/api/v1/concepts/concept_namespace/concept'
  concept_update = ConceptUpdate(
    insert=[
      ExampleIn(
        label=True,
        text='hello',
        origin=ExampleOrigin(
          dataset_namespace='dataset_namespace', dataset_name='dataset', dataset_row_id='d1'
        ),
      )
    ]
  )
  response = client.post(url, json=concept_update.model_dump())
  assert response.is_error is True
  assert response.status_code == 500
