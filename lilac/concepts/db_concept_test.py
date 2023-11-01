"""Tests for the the database concept."""

import os
from pathlib import Path
from typing import ClassVar, Generator, Iterable, Type, cast

import numpy as np
import pytest
from pytest_mock import MockerFixture
from sklearn.preprocessing import normalize
from typing_extensions import override

from ..data.dataset_duckdb import DatasetDuckDB
from ..db_manager import set_default_dataset_cls
from ..schema import Item, RichData, lilac_embedding
from ..signal import TextEmbeddingSignal, clear_signal_registry, register_signal
from .concept import (
  DRAFT_MAIN,
  Concept,
  ConceptMetadata,
  ConceptModel,
  ConceptType,
  DraftId,
  Example,
  ExampleIn,
  LogisticEmbeddingModel,
)
from .db_concept import (
  ConceptACL,
  ConceptDB,
  ConceptInfo,
  ConceptModelDB,
  ConceptUpdate,
  DiskConceptDB,
  DiskConceptModelDB,
)

ALL_CONCEPT_DBS = [DiskConceptDB]
ALL_CONCEPT_MODEL_DBS = [DiskConceptModelDB]


@pytest.fixture(autouse=True)
def set_project_dir(tmp_path: Path, mocker: MockerFixture) -> None:
  mocker.patch.dict(os.environ, {'LILAC_PROJECT_DIR': str(tmp_path)})


EMBEDDING_MAP: dict[str, list[float]] = {
  'not in concept': [1.0, 0.0, 0.0],
  'in concept': [0.9, 0.1, 0.0],
  'a new data point': [0.1, 0.2, 0.3],
  'a true draft point': [0.4, 0.5, 0.6],
  'a false draft point': [0.7, 0.8, 0.9],
}


class TestEmbedding(TextEmbeddingSignal):
  """A test embed function."""

  name: ClassVar[str] = 'test_embedding'

  @override
  def compute(self, data: Iterable[RichData]) -> Iterable[Item]:
    """Embed the examples, use a hashmap to the vector for simplicity."""
    for example in data:
      if example not in EMBEDDING_MAP:
        raise ValueError(f'Example "{str(example)}" not in embedding map')
      yield [lilac_embedding(0, len(example), np.array(EMBEDDING_MAP[cast(str, example)]))]


@pytest.fixture(scope='module', autouse=True)
def setup_teardown() -> Generator:
  set_default_dataset_cls(DatasetDuckDB)
  register_signal(TestEmbedding)

  # Unit test runs.
  yield

  # Teardown.
  clear_signal_registry()


@pytest.mark.parametrize('db_cls', ALL_CONCEPT_DBS)
class ConceptDBSuite:
  def test_list_lilac_concepts(self, db_cls: Type[ConceptDB]) -> None:
    db = db_cls()
    # Make sure a lilac concept exists in the default list.
    assert filter(lambda c: c.name == 'positive-sentiment' and c.namespace == 'lilac', db.list())

  def test_create_concept(self, db_cls: Type[ConceptDB]) -> None:
    db = db_cls()
    db.create(namespace='test', name='test_concept', type=ConceptType.TEXT)

    # Remove lilac concepts.
    concepts = list(filter(lambda c: c.namespace != 'lilac', db.list()))

    assert concepts == [
      ConceptInfo(
        namespace='test',
        name='test_concept',
        type=ConceptType.TEXT,
        drafts=[DRAFT_MAIN],
        acls=ConceptACL(read=True, write=True),
        metadata=ConceptMetadata(),
      )
    ]

    # Make sure list with drafts relects the drafts.
    train_data = [
      ExampleIn(label=False, text='not in concept', draft='test_draft'),
      ExampleIn(label=True, text='in concept', draft='test_draft'),
    ]
    db.edit('test', 'test_concept', ConceptUpdate(insert=train_data))

    # Remove lilac concepts.
    concepts = list(filter(lambda c: c.namespace != 'lilac', db.list()))

    assert concepts == [
      ConceptInfo(
        namespace='test',
        name='test_concept',
        type=ConceptType.TEXT,
        drafts=[DRAFT_MAIN, 'test_draft'],
        acls=ConceptACL(read=True, write=True),
        metadata=ConceptMetadata(),
      )
    ]

  def test_update_metadata(self, db_cls: Type[ConceptDB]) -> None:
    db = db_cls()
    db.create(namespace='test', name='test_concept', type=ConceptType.TEXT)

    # Remove lilac concepts.
    concepts = list(filter(lambda c: c.namespace != 'lilac', db.list()))

    assert concepts == [
      ConceptInfo(
        namespace='test',
        name='test_concept',
        type=ConceptType.TEXT,
        drafts=[DRAFT_MAIN],
        acls=ConceptACL(read=True, write=True),
        metadata=ConceptMetadata(),
      )
    ]

    db.update_metadata(
      'test',
      'test_concept',
      ConceptMetadata(is_public=True, tags=['test_tag'], description='test description'),
    )

    # Remove lilac concepts.
    concepts = list(filter(lambda c: c.namespace != 'lilac', db.list()))

    assert concepts == [
      ConceptInfo(
        namespace='test',
        name='test_concept',
        type=ConceptType.TEXT,
        drafts=[DRAFT_MAIN],
        acls=ConceptACL(read=True, write=True),
        metadata=ConceptMetadata(is_public=True, tags=['test_tag'], description='test description'),
      )
    ]

  def test_add_example(self, db_cls: Type[ConceptDB]) -> None:
    db = db_cls()
    namespace = 'test'
    concept_name = 'test_concept'
    train_data = [
      ExampleIn(label=False, text='not in concept'),
      ExampleIn(label=True, text='in concept'),
    ]
    db.create(namespace=namespace, name=concept_name, type=ConceptType.TEXT)
    db.edit(namespace, concept_name, ConceptUpdate(insert=train_data))

    concept = db.get(namespace, concept_name)

    assert concept is not None

    keys = list(concept.data.keys())
    assert concept == Concept(
      namespace=namespace,
      concept_name=concept_name,
      type=ConceptType.TEXT,
      data={
        keys[0]: Example(id=keys[0], label=False, text='not in concept'),
        keys[1]: Example(id=keys[1], label=True, text='in concept'),
      },
      version=1,
    )

    # Add a draft labels.
    db.edit(
      namespace,
      concept_name,
      ConceptUpdate(
        insert=[
          ExampleIn(label=False, text='really not in concept', draft='test_draft'),
          ExampleIn(label=True, text='really in concept', draft='test_draft'),
        ]
      ),
    )

    concept = db.get(namespace, concept_name)
    assert concept is not None

    keys = list(concept.data.keys())
    assert concept == Concept(
      namespace=namespace,
      concept_name=concept_name,
      type=ConceptType.TEXT,
      data={
        keys[0]: Example(id=keys[0], label=False, text='not in concept'),
        keys[1]: Example(id=keys[1], label=True, text='in concept'),
        keys[2]: Example(id=keys[2], label=False, text='really not in concept', draft='test_draft'),
        keys[3]: Example(id=keys[3], label=True, text='really in concept', draft='test_draft'),
      },
      version=2,
    )

  def test_update_concept(self, db_cls: Type[ConceptDB]) -> None:
    db = db_cls()
    namespace = 'test'
    concept_name = 'test_concept'
    train_data = [
      ExampleIn(label=False, text='not in concept'),
      ExampleIn(label=True, text='in concept'),
      ExampleIn(label=False, text='really not in concept', draft='test_draft'),
      ExampleIn(label=True, text='really in concept', draft='test_draft'),
    ]
    db.create(namespace=namespace, name=concept_name, type=ConceptType.TEXT)
    db.edit(namespace, concept_name, ConceptUpdate(insert=train_data))

    concept = db.get(namespace, concept_name)
    assert concept is not None

    keys = list(concept.data.keys())
    # Edit the first example.
    db.edit(
      namespace,
      concept_name,
      ConceptUpdate(update=[Example(id=keys[0], label=False, text='not in concept, updated')]),
    )
    concept = db.get(namespace, concept_name)

    assert concept == Concept(
      namespace=namespace,
      concept_name=concept_name,
      type=ConceptType.TEXT,
      data={
        # The first example should be updated alone.
        keys[0]: Example(id=keys[0], label=False, text='not in concept, updated'),
        keys[1]: Example(id=keys[1], label=True, text='in concept'),
        # Drafts are untouched.
        keys[2]: Example(id=keys[2], label=False, text='really not in concept', draft='test_draft'),
        keys[3]: Example(id=keys[3], label=True, text='really in concept', draft='test_draft'),
      },
      version=2,
    )

    # Edit the second example on the draft.
    db.edit(
      namespace,
      concept_name,
      ConceptUpdate(
        update=[
          Example(id=keys[3], label=True, text='really in concept, updated', draft='test_draft')
        ]
      ),
    )
    concept = db.get(namespace, concept_name)

    assert concept == Concept(
      namespace=namespace,
      concept_name=concept_name,
      type=ConceptType.TEXT,
      data={
        # Main remains the same.
        keys[0]: Example(id=keys[0], label=False, text='not in concept, updated'),
        keys[1]: Example(id=keys[1], label=True, text='in concept'),
        keys[2]: Example(id=keys[2], label=False, text='really not in concept', draft='test_draft'),
        keys[3]: Example(
          id=keys[3], label=True, text='really in concept, updated', draft='test_draft'
        ),
      },
      version=3,
    )

  def test_remove_concept(self, db_cls: Type[ConceptDB]) -> None:
    db = db_cls()
    namespace = 'test'
    concept_name = 'test_concept'
    db.create(namespace=namespace, name=concept_name, type=ConceptType.TEXT)

    train_data = [
      ExampleIn(label=False, text='not in concept'),
      ExampleIn(label=True, text='in concept'),
    ]
    db.edit(namespace, concept_name, ConceptUpdate(insert=train_data))
    concept = db.get(namespace, concept_name)

    db.remove(namespace, concept_name)

    concept = db.get(namespace, concept_name)

    assert concept is None

  def test_remove_concept_examples(self, db_cls: Type[ConceptDB]) -> None:
    db = db_cls()
    namespace = 'test'
    concept_name = 'test_concept'
    db.create(namespace=namespace, name=concept_name, type=ConceptType.TEXT)

    train_data = [
      ExampleIn(label=False, text='not in concept'),
      ExampleIn(label=True, text='in concept'),
    ]
    db.edit(namespace, concept_name, ConceptUpdate(insert=train_data))
    concept = db.get(namespace, concept_name)
    assert concept is not None

    keys = list(concept.data.keys())

    db.edit(namespace, concept_name, ConceptUpdate(remove=[keys[0]]))
    concept = db.get(namespace, concept_name)

    assert concept == Concept(
      namespace=namespace,
      concept_name=concept_name,
      type=ConceptType.TEXT,
      data={
        # key_0 was removed.
        keys[1]: Example(id=keys[1], label=True, text='in concept')
      },
      version=2,
    )

  def test_remove_concept_examples_draft(self, db_cls: Type[ConceptDB]) -> None:
    db = db_cls()
    namespace = 'test'
    concept_name = 'test_concept'
    train_data = [
      ExampleIn(label=False, text='not in concept'),
      ExampleIn(label=True, text='in concept'),
      ExampleIn(label=False, text='really not in concept', draft='test_draft'),
      ExampleIn(label=True, text='really in concept', draft='test_draft'),
    ]
    db.create(namespace=namespace, name=concept_name, type=ConceptType.TEXT)
    db.edit(namespace, concept_name, ConceptUpdate(insert=train_data))
    concept = db.get(namespace, concept_name)
    assert concept is not None

    keys = list(concept.data.keys())

    db.edit(namespace, concept_name, ConceptUpdate(remove=[keys[2]]))
    concept = db.get(namespace, concept_name)

    assert concept == Concept(
      namespace=namespace,
      concept_name=concept_name,
      type=ConceptType.TEXT,
      data={
        keys[0]: Example(id=keys[0], label=False, text='not in concept'),
        keys[1]: Example(id=keys[1], label=True, text='in concept'),
        # The first draft example is removed.
        keys[3]: Example(id=keys[3], label=True, text='really in concept', draft='test_draft'),
      },
      version=2,
    )

  def test_remove_invalid_id(self, db_cls: Type[ConceptDB]) -> None:
    db = db_cls()
    namespace = 'test'
    concept_name = 'test_concept'
    db.create(namespace=namespace, name=concept_name, type=ConceptType.TEXT)

    train_data = [
      ExampleIn(label=False, text='not in concept'),
      ExampleIn(label=True, text='in concept'),
      ExampleIn(label=False, text='really not in concept', draft='test_draft'),
      ExampleIn(label=True, text='really in concept', draft='test_draft'),
    ]
    db.edit(namespace, concept_name, ConceptUpdate(insert=train_data))

    with pytest.raises(ValueError, match='Example with id "invalid_id" does not exist'):
      db.edit(namespace, concept_name, ConceptUpdate(remove=['invalid_id']))

  def test_edit_before_creation(self, db_cls: Type[ConceptDB]) -> None:
    db = db_cls()
    namespace = 'test'
    concept_name = 'test_concept'

    with pytest.raises(
      ValueError, match='Concept with namespace "test" and name "test_concept" does not exist'
    ):
      db.edit(
        namespace,
        concept_name,
        ConceptUpdate(insert=[ExampleIn(label=False, text='not in concept')]),
      )

  def test_edit_invalid_id(self, db_cls: Type[ConceptDB]) -> None:
    db = db_cls()
    namespace = 'test'
    concept_name = 'test_concept'
    db.create(namespace=namespace, name=concept_name, type=ConceptType.TEXT)

    train_data = [
      ExampleIn(label=False, text='not in concept'),
      ExampleIn(label=True, text='in concept'),
    ]
    db.edit(namespace, concept_name, ConceptUpdate(insert=train_data))

    with pytest.raises(ValueError, match='Example with id "invalid_id" does not exist'):
      db.edit(
        namespace,
        concept_name,
        ConceptUpdate(update=[Example(id='invalid_id', label=False, text='not in concept')]),
      )

  def test_merge_draft(self, db_cls: Type[ConceptDB]) -> None:
    db = db_cls()
    namespace = 'test'
    concept_name = 'test_concept'
    db.create(namespace=namespace, name=concept_name, type=ConceptType.TEXT)

    train_data = [
      ExampleIn(label=True, text='hello'),
      ExampleIn(label=False, text='world'),
      ExampleIn(label=True, text='hello draft 1', draft='draft1'),
      ExampleIn(label=False, text='world draft 1', draft='draft1'),
      # Duplicate of main.
      ExampleIn(label=False, text='hello', draft='draft2'),
      ExampleIn(label=True, text='world draft 2', draft='draft2'),
    ]
    db.edit(namespace, concept_name, ConceptUpdate(insert=train_data))

    db.merge_draft(namespace, concept_name, 'draft1')

    concept = db.get(namespace, concept_name)
    assert concept is not None
    keys = list(concept.data.keys())

    assert (
      concept.model_dump()
      == Concept(
        namespace='test',
        concept_name='test_concept',
        type=ConceptType.TEXT,
        data={
          keys[0]: Example(id=keys[0], label=True, text='hello'),
          keys[1]: Example(id=keys[1], label=False, text='world'),
          # Draft examples are merged.
          keys[2]: Example(id=keys[2], label=True, text='hello draft 1'),
          keys[3]: Example(id=keys[3], label=False, text='world draft 1'),
          # Draft 2 is untouched.
          keys[4]: Example(id=keys[4], label=False, text='hello', draft='draft2'),
          keys[5]: Example(id=keys[5], label=True, text='world draft 2', draft='draft2'),
        },
        version=2,
      ).model_dump()
    )

    db.merge_draft(namespace, concept_name, 'draft2')

    concept = db.get(namespace, concept_name)
    assert concept is not None

    assert concept == Concept(
      namespace='test',
      concept_name='test_concept',
      type=ConceptType.TEXT,
      data={
        # The first example is a duplicate of the label from the draft, so it is removed.
        keys[1]: Example(id=keys[1], label=False, text='world'),
        # Draft examples are merged.
        keys[2]: Example(id=keys[2], label=True, text='hello draft 1'),
        keys[3]: Example(id=keys[3], label=False, text='world draft 1'),
        # Draft examples are merged.
        keys[4]: Example(id=keys[4], label=False, text='hello'),
        keys[5]: Example(id=keys[5], label=True, text='world draft 2'),
      },
      version=3,
    )


def _make_test_concept_model(
  concept_db: ConceptDB,
  model_db: ConceptModelDB,
  logistic_models: dict[DraftId, LogisticEmbeddingModel] = {},
) -> ConceptModel:
  namespace = 'test'
  concept_name = 'test_concept'
  concept_db.create(namespace=namespace, name=concept_name, type=ConceptType.TEXT)

  train_data = [
    ExampleIn(label=False, text='not in concept'),
    ExampleIn(label=True, text='in concept'),
  ]
  concept_db.edit(namespace, concept_name, ConceptUpdate(insert=train_data))
  model = model_db.create(namespace, concept_name, embedding_name='test_embedding')
  model._logistic_models = logistic_models
  model_db._save(model)
  return model


class TestLogisticModel(LogisticEmbeddingModel):
  @override
  def score_embeddings(self, embeddings: np.ndarray) -> np.ndarray:
    """Get the scores for the provided embeddings."""
    return np.array([0.1])

  @override
  def fit(self, embeddings: np.ndarray, labels: list[bool]) -> None:
    pass


@pytest.mark.parametrize('concept_db_cls', ALL_CONCEPT_DBS)
@pytest.mark.parametrize('model_db_cls', ALL_CONCEPT_MODEL_DBS)
class ConceptModelDBSuite:
  def test_save_and_get_model(
    self, concept_db_cls: Type[ConceptDB], model_db_cls: Type[ConceptModelDB]
  ) -> None:
    concept_db = concept_db_cls()
    model_db = model_db_cls(concept_db)
    model = _make_test_concept_model(concept_db, model_db)
    model = model_db.sync(model.namespace, model.concept_name, model.embedding_name)
    retrieved_model = model_db.get(
      namespace='test', concept_name='test_concept', embedding_name='test_embedding'
    )
    if not retrieved_model:
      retrieved_model = model_db.create(
        namespace='test', concept_name='test_concept', embedding_name='test_embedding'
      )
    assert retrieved_model.namespace == model.namespace
    assert retrieved_model.concept_name == model.concept_name
    assert retrieved_model.embedding_name == model.embedding_name
    assert retrieved_model.version == model.version

  def test_sync_model(
    self, concept_db_cls: Type[ConceptDB], model_db_cls: Type[ConceptModelDB], mocker: MockerFixture
  ) -> None:
    concept_db = concept_db_cls()
    model_db = model_db_cls(concept_db)
    logistic_model = TestLogisticModel()
    score_embeddings_mock = mocker.spy(TestLogisticModel, 'score_embeddings')
    fit_mock = mocker.spy(TestLogisticModel, 'fit')

    model = _make_test_concept_model(
      concept_db, model_db, logistic_models={DRAFT_MAIN: logistic_model}
    )

    assert model_db.in_sync(model) is False
    assert score_embeddings_mock.call_count == 0
    assert fit_mock.call_count == 0

    model = model_db.sync(model.namespace, model.concept_name, model.embedding_name)

    assert model_db.in_sync(model) is True
    assert score_embeddings_mock.call_count == 0
    assert fit_mock.call_count == 1

  def test_out_of_sync_model(
    self, concept_db_cls: Type[ConceptDB], model_db_cls: Type[ConceptModelDB], mocker: MockerFixture
  ) -> None:
    concept_db = concept_db_cls()
    model_db = model_db_cls(concept_db)
    score_embeddings_mock = mocker.spy(TestLogisticModel, 'score_embeddings')
    fit_mock = mocker.spy(TestLogisticModel, 'fit')
    logistic_model = TestLogisticModel()
    model = _make_test_concept_model(
      concept_db, model_db, logistic_models={DRAFT_MAIN: logistic_model}
    )
    model = model_db.sync(model.namespace, model.concept_name, model.embedding_name)
    assert model_db.in_sync(model) is True
    assert score_embeddings_mock.call_count == 0
    assert fit_mock.call_count == 1

    (called_model, called_embeddings, called_labels) = fit_mock.call_args_list[-1].args
    assert called_model == logistic_model
    np.testing.assert_array_equal(
      called_embeddings,
      normalize(np.array([EMBEDDING_MAP['not in concept'], EMBEDDING_MAP['in concept']])),
    )
    assert called_labels == [False, True]

    # Edit the concept.
    concept_db.edit(
      'test',
      'test_concept',
      ConceptUpdate(insert=[ExampleIn(label=False, text='a new data point')]),
    )

    # Make sure the model is out of sync.
    assert model_db.in_sync(model) is False
    assert score_embeddings_mock.call_count == 0
    assert fit_mock.call_count == 1

    model = model_db.sync(model.namespace, model.concept_name, model.embedding_name)
    assert model_db.in_sync(model) is True
    assert score_embeddings_mock.call_count == 0
    assert fit_mock.call_count == 2
    # Fit is called again with new points on main only.
    (called_model, called_embeddings, called_labels) = fit_mock.call_args_list[-1].args
    assert called_model == logistic_model
    np.testing.assert_array_equal(
      called_embeddings,
      normalize(
        np.array(
          [
            EMBEDDING_MAP['not in concept'],
            EMBEDDING_MAP['in concept'],
            EMBEDDING_MAP['a new data point'],
          ]
        )
      ),
    )
    assert called_labels == [False, True, False]

  def test_out_of_sync_draft_model(
    self, concept_db_cls: Type[ConceptDB], model_db_cls: Type[ConceptModelDB], mocker: MockerFixture
  ) -> None:
    concept_db = concept_db_cls()
    model_db = model_db_cls(concept_db)
    score_embeddings_mock = mocker.spy(TestLogisticModel, 'score_embeddings')
    fit_mock = mocker.spy(TestLogisticModel, 'fit')
    main_model = TestLogisticModel()
    draft_model = TestLogisticModel()
    model = _make_test_concept_model(
      concept_db, model_db, logistic_models={DRAFT_MAIN: main_model, 'test_draft': draft_model}
    )
    model = model_db.sync(model.namespace, model.concept_name, model.embedding_name)
    assert model_db.in_sync(model) is True
    assert score_embeddings_mock.call_count == 0
    assert fit_mock.call_count == 1

    # Make sure drafts cause the model to be out of sync.
    concept_db.edit(
      'test',
      'test_concept',
      ConceptUpdate(
        insert=[
          ExampleIn(label=True, text='a true draft point', draft='test_draft'),
          ExampleIn(label=False, text='a false draft point', draft='test_draft'),
          # This point exists in main, but we switched the label.
          ExampleIn(label=False, text='in concept', draft='test_draft'),
        ]
      ),
    )

    # Make sure the model is out of sync.
    assert model_db.in_sync(model) is False
    assert score_embeddings_mock.call_count == 0
    assert fit_mock.call_count == 1

    model = model_db.sync(model.namespace, model.concept_name, model.embedding_name)
    assert model_db.in_sync(model) is True
    assert score_embeddings_mock.call_count == 0
    assert fit_mock.call_count == 3  # Fit is called on both the draft, and main.

    # Fit is called again with the same points.
    (
      (called_model, called_embeddings, called_labels),
      (called_draft_model, called_draft_embeddings, called_draft_labels),
    ) = (c.args for c in fit_mock.call_args_list[-2:])

    # The draft model is called with the data from main, and the data from draft.
    assert called_draft_model == draft_model
    np.testing.assert_array_equal(
      called_draft_embeddings,
      normalize(
        np.array(
          [
            EMBEDDING_MAP['a true draft point'],
            EMBEDDING_MAP['a false draft point'],
            EMBEDDING_MAP['in concept'],
            EMBEDDING_MAP['not in concept'],
          ]
        )
      ),
    )
    assert called_draft_labels == [
      True,
      False,
      # This was overriden by the draft.
      False,
      False,
    ]

    # The main model was fit without the data from the draft.
    assert called_model == main_model
    np.testing.assert_array_equal(
      called_embeddings,
      normalize(np.array([EMBEDDING_MAP['not in concept'], EMBEDDING_MAP['in concept']])),
    )
    assert called_labels == [False, True]

  def test_embedding_not_found_in_map(
    self, concept_db_cls: Type[ConceptDB], model_db_cls: Type[ConceptModelDB]
  ) -> None:
    concept_db = concept_db_cls()
    model_db = model_db_cls(concept_db)
    model = _make_test_concept_model(concept_db, model_db)
    model = model_db.sync(model.namespace, model.concept_name, model.embedding_name)

    # Edit the concept.
    concept_db.edit(
      'test', 'test_concept', ConceptUpdate(insert=[ExampleIn(label=False, text='unknown text')])
    )

    # Make sure the model is out of sync.
    assert model_db.in_sync(model) is False

    with pytest.raises(ValueError, match='Example "unknown text" not in embedding map'):
      model_db.sync(model.namespace, model.concept_name, model.embedding_name)
