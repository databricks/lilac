"""Tests for the the database concept."""

from pathlib import Path
from typing import Generator, Iterable, Optional, Type, cast

import numpy as np
import pytest
from pytest_mock import MockerFixture
from typing_extensions import override

from ..config import CONFIG
from ..schema import RichData, SignalInputType, SignalOut
from ..signals.signal import TextEmbeddingSignal, clear_signal_registry, register_signal
from .concept import (
  DRAFT_MAIN,
  Concept,
  ConceptModel,
  ConceptModelManager,
  DraftId,
  Example,
  ExampleIn,
  Sensitivity,
)
from .db_concept import (
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
def set_data_path(tmp_path: Path) -> Generator:
  data_path = CONFIG['LILAC_DATA_PATH']
  CONFIG['LILAC_DATA_PATH'] = str(tmp_path)

  yield

  CONFIG['LILAC_DATA_PATH'] = data_path or ''


EMBEDDING_MAP: dict[str, list[float]] = {
  'not in concept': [1.0, 0.0, 0.0],
  'in concept': [0.9, 0.1, 0.0],
  'a new data point': [0.1, 0.2, 0.3],
  'a true draft point': [0.4, 0.5, 0.6],
  'a false draft point': [0.7, 0.8, 0.9],
}


class TestEmbedding(TextEmbeddingSignal):
  """A test embed function."""
  name = 'test_embedding'

  @override
  def compute(self, data: Iterable[RichData]) -> Iterable[SignalOut]:
    """Embed the examples, use a hashmap to the vector for simplicity."""
    for example in data:
      if example not in EMBEDDING_MAP:
        raise ValueError(f'Example "{str(example)}" not in embedding map')
    yield from [np.array(EMBEDDING_MAP[cast(str, example)]) for example in data]


@pytest.fixture(scope='module', autouse=True)
def setup_teardown() -> Generator:
  register_signal(TestEmbedding)

  # Unit test runs.
  yield

  # Teardown.
  clear_signal_registry()


@pytest.mark.parametrize('db_cls', ALL_CONCEPT_DBS)
class ConceptDBSuite:

  def test_create_concept(self, db_cls: Type[ConceptDB]) -> None:
    db = db_cls()
    db.create(namespace='test', name='test_concept', type=SignalInputType.TEXT)

    assert db.list() == [
      ConceptInfo(
        namespace='test', name='test_concept', type=SignalInputType.TEXT, drafts=[DRAFT_MAIN])
    ]

    # Make sure list with drafts relects the drafts.
    train_data = [
      ExampleIn(label=False, text='not in concept', draft='test_draft'),
      ExampleIn(label=True, text='in concept', draft='test_draft')
    ]
    db.edit('test', 'test_concept', ConceptUpdate(insert=train_data))

    assert db.list() == [
      ConceptInfo(
        namespace='test',
        name='test_concept',
        type=SignalInputType.TEXT,
        drafts=[DRAFT_MAIN, 'test_draft'])
    ]

  def test_add_example(self, db_cls: Type[ConceptDB]) -> None:
    db = db_cls()
    namespace = 'test'
    concept_name = 'test_concept'
    train_data = [
      ExampleIn(label=False, text='not in concept'),
      ExampleIn(label=True, text='in concept')
    ]
    db.create(namespace=namespace, name=concept_name, type=SignalInputType.TEXT)
    db.edit(namespace, concept_name, ConceptUpdate(insert=train_data))

    concept = db.get(namespace, concept_name)

    assert concept is not None

    keys = list(concept.data.keys())
    assert concept == Concept(
      namespace=namespace,
      concept_name=concept_name,
      type=SignalInputType.TEXT,
      data={
        keys[0]: Example(id=keys[0], label=False, text='not in concept'),
        keys[1]: Example(id=keys[1], label=True, text='in concept')
      },
      version=1)

    # Add a draft labels.
    db.edit(
      namespace, concept_name,
      ConceptUpdate(insert=[
        ExampleIn(label=False, text='really not in concept', draft='test_draft'),
        ExampleIn(label=True, text='really in concept', draft='test_draft')
      ]))

    concept = db.get(namespace, concept_name)
    assert concept is not None

    keys = list(concept.data.keys())
    assert concept == Concept(
      namespace=namespace,
      concept_name=concept_name,
      type=SignalInputType.TEXT,
      data={
        keys[0]: Example(id=keys[0], label=False, text='not in concept'),
        keys[1]: Example(id=keys[1], label=True, text='in concept'),
        keys[2]: Example(id=keys[2], label=False, text='really not in concept', draft='test_draft'),
        keys[3]: Example(id=keys[3], label=True, text='really in concept', draft='test_draft'),
      },
      version=2)

  def test_update_concept(self, db_cls: Type[ConceptDB]) -> None:
    db = db_cls()
    namespace = 'test'
    concept_name = 'test_concept'
    train_data = [
      ExampleIn(label=False, text='not in concept'),
      ExampleIn(label=True, text='in concept'),
      ExampleIn(label=False, text='really not in concept', draft='test_draft'),
      ExampleIn(label=True, text='really in concept', draft='test_draft')
    ]
    db.create(namespace=namespace, name=concept_name, type=SignalInputType.TEXT)
    db.edit(namespace, concept_name, ConceptUpdate(insert=train_data))

    concept = db.get(namespace, concept_name)
    assert concept is not None

    keys = list(concept.data.keys())
    # Edit the first example.
    db.edit(
      namespace, concept_name,
      ConceptUpdate(update=[Example(id=keys[0], label=False, text='not in concept, updated')]))
    concept = db.get(namespace, concept_name)

    assert concept == Concept(
      namespace=namespace,
      concept_name=concept_name,
      type=SignalInputType.TEXT,
      data={
        # The first example should be updated alone.
        keys[0]: Example(id=keys[0], label=False, text='not in concept, updated'),
        keys[1]: Example(id=keys[1], label=True, text='in concept'),
        # Drafts are untouched.
        keys[2]: Example(id=keys[2], label=False, text='really not in concept', draft='test_draft'),
        keys[3]: Example(id=keys[3], label=True, text='really in concept', draft='test_draft'),
      },
      version=2)

    # Edit the second example on the draft.
    db.edit(
      namespace, concept_name,
      ConceptUpdate(update=[
        Example(id=keys[3], label=True, text='really in concept, updated', draft='test_draft')
      ]))
    concept = db.get(namespace, concept_name)

    assert concept == Concept(
      namespace=namespace,
      concept_name=concept_name,
      type=SignalInputType.TEXT,
      data={
        # Main remains the same.
        keys[0]: Example(id=keys[0], label=False, text='not in concept, updated'),
        keys[1]: Example(id=keys[1], label=True, text='in concept'),
        keys[2]: Example(id=keys[2], label=False, text='really not in concept', draft='test_draft'),
        keys[3]: Example(
          id=keys[3], label=True, text='really in concept, updated', draft='test_draft'),
      },
      version=3)

  def test_remove_concept(self, db_cls: Type[ConceptDB]) -> None:
    db = db_cls()
    namespace = 'test'
    concept_name = 'test_concept'
    db.create(namespace=namespace, name=concept_name, type=SignalInputType.TEXT)

    train_data = [
      ExampleIn(label=False, text='not in concept'),
      ExampleIn(label=True, text='in concept')
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
    db.create(namespace=namespace, name=concept_name, type=SignalInputType.TEXT)

    train_data = [
      ExampleIn(label=False, text='not in concept'),
      ExampleIn(label=True, text='in concept')
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
      type=SignalInputType.TEXT,
      data={
        # key_0 was removed.
        keys[1]: Example(id=keys[1], label=True, text='in concept')
      },
      version=2)

  def test_remove_concept_examples_draft(self, db_cls: Type[ConceptDB]) -> None:
    db = db_cls()
    namespace = 'test'
    concept_name = 'test_concept'
    train_data = [
      ExampleIn(label=False, text='not in concept'),
      ExampleIn(label=True, text='in concept'),
      ExampleIn(label=False, text='really not in concept', draft='test_draft'),
      ExampleIn(label=True, text='really in concept', draft='test_draft')
    ]
    db.create(namespace=namespace, name=concept_name, type=SignalInputType.TEXT)
    db.edit(namespace, concept_name, ConceptUpdate(insert=train_data))
    concept = db.get(namespace, concept_name)
    assert concept is not None

    keys = list(concept.data.keys())

    db.edit(namespace, concept_name, ConceptUpdate(remove=[keys[2]]))
    concept = db.get(namespace, concept_name)

    assert concept == Concept(
      namespace=namespace,
      concept_name=concept_name,
      type=SignalInputType.TEXT,
      data={
        keys[0]: Example(id=keys[0], label=False, text='not in concept'),
        keys[1]: Example(id=keys[1], label=True, text='in concept'),
        # The first draft example is removed.
        keys[3]: Example(id=keys[3], label=True, text='really in concept', draft='test_draft'),
      },
      version=2)

  def test_remove_invalid_id(self, db_cls: Type[ConceptDB]) -> None:
    db = db_cls()
    namespace = 'test'
    concept_name = 'test_concept'
    db.create(namespace=namespace, name=concept_name, type=SignalInputType.TEXT)

    train_data = [
      ExampleIn(label=False, text='not in concept'),
      ExampleIn(label=True, text='in concept'),
      ExampleIn(label=False, text='really not in concept', draft='test_draft'),
      ExampleIn(label=True, text='really in concept', draft='test_draft')
    ]
    db.edit(namespace, concept_name, ConceptUpdate(insert=train_data))

    with pytest.raises(ValueError, match='Example with id "invalid_id" does not exist'):
      db.edit(namespace, concept_name, ConceptUpdate(remove=['invalid_id']))

  def test_edit_before_creation(self, db_cls: Type[ConceptDB]) -> None:
    db = db_cls()
    namespace = 'test'
    concept_name = 'test_concept'

    with pytest.raises(
        ValueError, match='Concept with namespace "test" and name "test_concept" does not exist'):
      db.edit(namespace, concept_name,
              ConceptUpdate(insert=[
                ExampleIn(label=False, text='not in concept'),
              ]))

  def test_edit_invalid_id(self, db_cls: Type[ConceptDB]) -> None:
    db = db_cls()
    namespace = 'test'
    concept_name = 'test_concept'
    db.create(namespace=namespace, name=concept_name, type=SignalInputType.TEXT)

    train_data = [
      ExampleIn(label=False, text='not in concept'),
      ExampleIn(label=True, text='in concept')
    ]
    db.edit(namespace, concept_name, ConceptUpdate(insert=train_data))

    with pytest.raises(ValueError, match='Example with id "invalid_id" does not exist'):
      db.edit(namespace, concept_name,
              ConceptUpdate(update=[Example(id='invalid_id', label=False, text='not in concept')]))

  def test_merge_draft(self, db_cls: Type[ConceptDB]) -> None:
    db = db_cls()
    namespace = 'test'
    concept_name = 'test_concept'
    db.create(namespace=namespace, name=concept_name, type=SignalInputType.TEXT)

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

    assert concept.dict() == Concept(
      namespace='test',
      concept_name='test_concept',
      type=SignalInputType.TEXT,
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
      version=2).dict()

    db.merge_draft(namespace, concept_name, 'draft2')

    concept = db.get(namespace, concept_name)
    assert concept is not None

    assert concept == Concept(
      namespace='test',
      concept_name='test_concept',
      type=SignalInputType.TEXT,
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
      version=3)


def _make_test_concept_model_manager(
    concept_db: ConceptDB,
    model_db: ConceptModelDB,
    concept_models: Optional[dict[DraftId, ConceptModel]] = {}) -> ConceptModelManager:
  namespace = 'test'
  concept_name = 'test_concept'
  concept_db.create(namespace=namespace, name=concept_name, type=SignalInputType.TEXT)

  train_data = [
    ExampleIn(label=False, text='not in concept'),
    ExampleIn(label=True, text='in concept')
  ]
  concept_db.edit(namespace, concept_name, ConceptUpdate(insert=train_data))
  return ConceptModelManager(
    namespace='test',
    concept_name='test_concept',
    embedding_name='test_embedding',
    concept_models=concept_models)


class TestConceptModel(ConceptModel):

  @override
  def score_embeddings(self, embeddings: np.ndarray, sensitivity: Sensitivity) -> np.ndarray:
    """Get the scores for the provided embeddings."""
    return np.array([.1])

  @override
  def fit(self, embeddings: np.ndarray, labels: list[bool]) -> None:
    pass


@pytest.mark.parametrize('concept_db_cls', ALL_CONCEPT_DBS)
@pytest.mark.parametrize('model_db_cls', ALL_CONCEPT_MODEL_DBS)
class ConceptModelDBSuite:

  def test_save_and_get_model_manager(self, concept_db_cls: Type[ConceptDB],
                                      model_db_cls: Type[ConceptModelDB]) -> None:
    concept_db = concept_db_cls()
    model_db = model_db_cls(concept_db)
    manager = _make_test_concept_model_manager(concept_db, model_db)

    model_db.sync(manager)
    retrieved_manager = model_db.get(
      namespace='test', concept_name='test_concept', embedding_name='test_embedding')

    assert retrieved_manager.get_model(DRAFT_MAIN) == manager.get_model(DRAFT_MAIN)

  def test_sync_model(self, concept_db_cls: Type[ConceptDB], model_db_cls: Type[ConceptModelDB],
                      mocker: MockerFixture) -> None:

    concept_db = concept_db_cls()
    model_db = model_db_cls(concept_db)
    model = TestConceptModel(
      namespace='test', concept_name='test_concept', embedding_name='test_embedding')
    score_embeddings_mock = mocker.spy(TestConceptModel, 'score_embeddings')
    fit_mock = mocker.spy(TestConceptModel, 'fit')

    manager = _make_test_concept_model_manager(
      concept_db, model_db, concept_models={DRAFT_MAIN: model})

    assert model_db.in_sync(manager) is False
    assert score_embeddings_mock.call_count == 0
    assert fit_mock.call_count == 0

    model_db.sync(manager)

    assert model_db.in_sync(manager) is True
    assert score_embeddings_mock.call_count == 0
    assert fit_mock.call_count == 1

  def test_out_of_sync_model(self, concept_db_cls: Type[ConceptDB],
                             model_db_cls: Type[ConceptModelDB], mocker: MockerFixture) -> None:
    concept_db = concept_db_cls()
    model_db = model_db_cls(concept_db)
    score_embeddings_mock = mocker.spy(TestConceptModel, 'score_embeddings')
    fit_mock = mocker.spy(TestConceptModel, 'fit')
    model = TestConceptModel(
      namespace='test', concept_name='test_concept', embedding_name='test_embedding')
    manager = _make_test_concept_model_manager(
      concept_db, model_db, concept_models={DRAFT_MAIN: model})
    model_db.sync(manager)
    assert model_db.in_sync(manager) is True
    assert score_embeddings_mock.call_count == 0
    assert fit_mock.call_count == 1

    (called_model, called_embeddings, called_labels) = fit_mock.call_args_list[-1].args
    assert called_model == model
    np.testing.assert_array_equal(
      called_embeddings, np.array([EMBEDDING_MAP['not in concept'], EMBEDDING_MAP['in concept']]))
    assert called_labels == [False, True]

    # Edit the concept.
    concept_db.edit('test', 'test_concept',
                    ConceptUpdate(insert=[ExampleIn(label=False, text='a new data point')]))

    # Make sure the manager is out of sync.
    assert model_db.in_sync(manager) is False
    assert score_embeddings_mock.call_count == 0
    assert fit_mock.call_count == 1

    model_db.sync(manager)
    assert model_db.in_sync(manager) is True
    assert score_embeddings_mock.call_count == 0
    assert fit_mock.call_count == 2
    # Fit is called again with new points on main only.
    (called_model, called_embeddings, called_labels) = fit_mock.call_args_list[-1].args
    assert called_model == model
    np.testing.assert_array_equal(
      called_embeddings,
      np.array([
        EMBEDDING_MAP['not in concept'], EMBEDDING_MAP['in concept'],
        EMBEDDING_MAP['a new data point']
      ]))
    assert called_labels == [False, True, False]

  def test_out_of_sync_draft_model(self, concept_db_cls: Type[ConceptDB],
                                   model_db_cls: Type[ConceptModelDB],
                                   mocker: MockerFixture) -> None:
    concept_db = concept_db_cls()
    model_db = model_db_cls(concept_db)
    score_embeddings_mock = mocker.spy(TestConceptModel, 'score_embeddings')
    fit_mock = mocker.spy(TestConceptModel, 'fit')
    model = TestConceptModel(
      namespace='test', concept_name='test_concept', embedding_name='test_embedding')
    draft_model = TestConceptModel(
      namespace='test', concept_name='test_concept', embedding_name='test_embedding')
    manager = _make_test_concept_model_manager(
      concept_db, model_db, concept_models={
        DRAFT_MAIN: model,
        'test_draft': draft_model
      })
    model_db.sync(manager)
    assert model_db.in_sync(manager) is True
    assert score_embeddings_mock.call_count == 0
    assert fit_mock.call_count == 1

    # Make sure drafts cause the model to be out of sync.
    concept_db.edit(
      'test',
      'test_concept',
      ConceptUpdate(insert=[
        ExampleIn(label=True, text='a true draft point', draft='test_draft'),
        ExampleIn(label=False, text='a false draft point', draft='test_draft'),
        # This point exists in main, but we switched the label.
        ExampleIn(label=False, text='in concept', draft='test_draft'),
      ]))

    # Make sure the manager is out of sync.
    assert model_db.in_sync(manager) is False
    assert score_embeddings_mock.call_count == 0
    assert fit_mock.call_count == 1

    model_db.sync(manager)
    assert model_db.in_sync(manager) is True
    assert score_embeddings_mock.call_count == 0
    assert fit_mock.call_count == 3  # Fit is called on both the draft, and main.

    # Fit is called again with the same points.
    ((called_model, called_embeddings, called_labels),
     (called_draft_model, called_draft_embeddings, called_draft_labels)) = (
       c.args for c in fit_mock.call_args_list[-2:])

    # The draft model is called with the data from main, and the data from draft.
    assert called_draft_model == draft_model
    np.testing.assert_array_equal(
      called_draft_embeddings,
      np.array([
        EMBEDDING_MAP['a true draft point'], EMBEDDING_MAP['a false draft point'],
        EMBEDDING_MAP['in concept'], EMBEDDING_MAP['not in concept']
      ]))
    assert called_draft_labels == [
      True,
      False,
      # This was overriden by the draft.
      False,
      False
    ]

    # The main model was fit without the data from the draft.
    assert called_model == model
    np.testing.assert_array_equal(
      called_embeddings, np.array([EMBEDDING_MAP['not in concept'], EMBEDDING_MAP['in concept']]))
    assert called_labels == [False, True]

  def test_embedding_not_found_in_map(self, concept_db_cls: Type[ConceptDB],
                                      model_db_cls: Type[ConceptModelDB]) -> None:
    concept_db = concept_db_cls()
    model_db = model_db_cls(concept_db)
    model = _make_test_concept_model_manager(concept_db, model_db)
    model_db.sync(model)

    # Edit the concept.
    concept_db.edit('test', 'test_concept',
                    ConceptUpdate(insert=[ExampleIn(label=False, text='unknown text')]))

    # Make sure the model is out of sync.
    assert model_db.in_sync(model) is False

    with pytest.raises(ValueError, match='Example "unknown text" not in embedding map'):
      model_db.sync(model)
      model_db.sync(model)
