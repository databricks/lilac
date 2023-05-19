"""Tests for the the database concept."""

from pathlib import Path
from typing import Generator, Iterable, Type, cast

import numpy as np
import pytest
from typing_extensions import override

from ..config import CONFIG
from ..schema import RichData, SignalOut
from ..signals.signal import TextEmbeddingSignal, clear_signal_registry, register_signal
from .concept import DRAFT_MAIN, Concept, ConceptModelManager, Example, ExampleIn
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
    db.create(namespace='test', name='test_concept', type='text')

    assert db.list() == [ConceptInfo(namespace='test', name='test_concept', type='text', drafts=[])]

  def test_add_concept(self, db_cls: Type[ConceptDB]) -> None:
    db = db_cls()
    namespace = 'test'
    concept_name = 'test_concept'
    train_data = [
      ExampleIn(label=False, text='not in concept'),
      ExampleIn(label=True, text='in concept')
    ]
    db.create(namespace=namespace, name=concept_name, type='text')
    db.edit(namespace, concept_name, ConceptUpdate(insert=train_data))

    concept = db.get(namespace, concept_name)

    assert concept is not None
    print(concept.data)

    key_0 = list(concept.data[DRAFT_MAIN].keys())[0]
    key_1 = list(concept.data[DRAFT_MAIN].keys())[1]
    assert concept == Concept(
      namespace=namespace,
      concept_name=concept_name,
      type='text',
      data={
        DRAFT_MAIN: {
          key_0: Example(id=key_0, label=False, text='not in concept'),
          key_1: Example(id=key_1, label=True, text='in concept')
        }
      },
      version=1)

  def test_update_concept(self, db_cls: Type[ConceptDB]) -> None:
    db = db_cls()
    namespace = 'test'
    concept_name = 'test_concept'
    train_data = [
      ExampleIn(label=False, text='not in concept'),
      ExampleIn(label=True, text='in concept')
    ]
    db.create(namespace=namespace, name=concept_name, type='text')
    db.edit(namespace, concept_name, ConceptUpdate(insert=train_data))

    concept = db.get(namespace, concept_name)

    assert concept is not None

    example = list(concept.data.values())[0]

    concept = db.edit(
      namespace, concept_name,
      ConceptUpdate(update=[Example(id=example.id, label=False, text='not in concept, updated')]))

    updated_example = concept.data[example.id]
    assert updated_example == Example(id=example.id, label=False, text='not in concept, updated')

  def test_remove_concept(self, db_cls: Type[ConceptDB]) -> None:
    db = db_cls()
    namespace = 'test'
    concept_name = 'test_concept'
    db.create(namespace=namespace, name=concept_name, type='text')

    train_data = [
      ExampleIn(label=False, text='not in concept'),
      ExampleIn(label=True, text='in concept')
    ]
    db.edit(namespace, concept_name, ConceptUpdate(insert=train_data))

    db.remove(namespace, concept_name)

    concept = db.get(namespace, concept_name)

    assert concept is None

  def test_remove_concept_examples(self, db_cls: Type[ConceptDB]) -> None:
    db = db_cls()
    namespace = 'test'
    concept_name = 'test_concept'
    db.create(namespace=namespace, name=concept_name, type='text')

    train_data = [
      ExampleIn(label=False, text='not in concept'),
      ExampleIn(label=True, text='in concept')
    ]
    db.edit(namespace, concept_name, ConceptUpdate(insert=train_data))

    concept = db.get(namespace, concept_name)

    assert concept is not None

    example = list(concept.data[DRAFT_MAIN].values())[0]

    db.edit(namespace, concept_name, ConceptUpdate(remove=[ExampleRemove(id=example.id)]))

    concept = db.get(namespace, concept_name)

    assert concept is not None
    assert len(concept.data.keys()) == 1
    assert example.id not in concept.data.keys()

  def test_remove_invalid_id(self, db_cls: Type[ConceptDB]) -> None:
    db = db_cls()
    namespace = 'test'
    concept_name = 'test_concept'
    db.create(namespace=namespace, name=concept_name, type='text')

    train_data = [
      ExampleIn(label=False, text='not in concept'),
      ExampleIn(label=True, text='in concept')
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
    db.create(namespace=namespace, name=concept_name, type='text')

    train_data = [
      ExampleIn(label=False, text='not in concept'),
      ExampleIn(label=True, text='in concept')
    ]
    db.edit(namespace, concept_name, ConceptUpdate(insert=train_data))

    with pytest.raises(ValueError, match='Example with id "invalid_id" does not exist'):
      db.edit(namespace, concept_name,
              ConceptUpdate(update=[Example(id='invalid_id', label=False, text='not in concept')]))


def _make_test_concept_model_manager(concept_db: ConceptDB,
                                     model_db: ConceptModelDB) -> ConceptModelManager:
  namespace = 'test'
  concept_name = 'test_concept'
  concept_db.create(namespace=namespace, name=concept_name, type='text')

  train_data = [
    ExampleIn(label=False, text='not in concept'),
    ExampleIn(label=True, text='in concept')
  ]
  concept_db.edit(namespace, concept_name, ConceptUpdate(insert=train_data))
  return ConceptModelManager(
    namespace='test', concept_name='test_concept', embedding_name='test_embedding')


@pytest.mark.parametrize('concept_db_cls', ALL_CONCEPT_DBS)
@pytest.mark.parametrize('model_db_cls', ALL_CONCEPT_MODEL_DBS)
class ConceptModelDBSuite:

  def test_save_and_get_model(self, concept_db_cls: Type[ConceptDB],
                              model_db_cls: Type[ConceptModelDB]) -> None:
    concept_db = concept_db_cls()
    model_db = model_db_cls(concept_db)
    model = _make_test_concept_model_manager(concept_db, model_db)

    model_db.sync(model)
    retrieved_model = model_db.get(
      namespace='test', concept_name='test_concept', embedding_name='test_embedding')

    assert retrieved_model == model

  def test_sync_model(self, concept_db_cls: Type[ConceptDB],
                      model_db_cls: Type[ConceptModelDB]) -> None:
    concept_db = concept_db_cls()
    model_db = model_db_cls(concept_db)
    model = _make_test_concept_model_manager(concept_db, model_db)

    assert model_db.in_sync(model) is False
    model_db.sync(model)
    assert model_db.in_sync(model) is True

  def test_out_of_sync_model(self, concept_db_cls: Type[ConceptDB],
                             model_db_cls: Type[ConceptModelDB]) -> None:
    concept_db = concept_db_cls()
    model_db = model_db_cls(concept_db)
    model = _make_test_concept_model_manager(concept_db, model_db)
    model_db.sync(model)
    assert model_db.in_sync(model) is True

    # Edit the concept.
    concept_db.edit('test', 'test_concept',
                    ConceptUpdate(insert=[ExampleIn(label=False, text='a new data point')]))

    # Make sure the model is out of sync.
    assert model_db.in_sync(model) is False

    model_db.sync(model)
    assert model_db.in_sync(model) is True

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
