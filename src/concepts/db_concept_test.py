"""Tests for the the database concept."""

import os
from pathlib import Path
from typing import Generator, Type

import pytest

from .concept import Example, ExampleIn
from .db_concept import ConceptDB, ConceptUpdate, DiskConceptDB

ALL_CONCEPT_DBS = [DiskConceptDB]


@pytest.fixture(autouse=True)
def set_data_path(tmp_path: Path) -> Generator:
  data_path = os.environ.get('LILAC_DATA_PATH', None)
  os.environ['LILAC_DATA_PATH'] = str(tmp_path)

  yield

  os.environ['LILAC_DATA_PATH'] = data_path or ''


@pytest.mark.parametrize('db_cls', ALL_CONCEPT_DBS)
class DBConceptSuite:

  def test_add_concept(self, db_cls: Type[ConceptDB]) -> None:
    db = db_cls()
    namespace = 'test'
    concept_name = 'test_concept'
    train_data = [
        ExampleIn(label=False, text='not in concept'),
        ExampleIn(label=True, text='in concept')
    ]
    db.edit(namespace, concept_name, ConceptUpdate(insert=train_data))

    concept = db.get(namespace, concept_name)

    assert concept is not None
    assert concept.namespace == namespace
    assert concept.concept_name == concept_name
    assert concept.type == 'text'
    assert len(concept.data.keys()) == 2
    for example in concept.data.values():
      assert example.label is not None
      assert example.text in ['not in concept', 'in concept']

  def test_update_concept(self, db_cls: Type[ConceptDB]) -> None:
    db = db_cls()
    namespace = 'test'
    concept_name = 'test_concept'
    train_data = [
        ExampleIn(label=False, text='not in concept'),
        ExampleIn(label=True, text='in concept')
    ]
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
    train_data = [
        ExampleIn(label=False, text='not in concept'),
        ExampleIn(label=True, text='in concept')
    ]
    db.edit(namespace, concept_name, ConceptUpdate(insert=train_data))

    concept = db.get(namespace, concept_name)

    assert concept is not None

    example = list(concept.data.values())[0]

    db.edit(namespace, concept_name, ConceptUpdate(remove=[example.id]))

    concept = db.get(namespace, concept_name)

    assert concept is not None
    assert len(concept.data.keys()) == 1
    assert example.id not in concept.data.keys()

  def test_remove_invalid_id(self, db_cls: Type[ConceptDB]) -> None:
    db = db_cls()
    namespace = 'test'
    concept_name = 'test_concept'
    train_data = [
        ExampleIn(label=False, text='not in concept'),
        ExampleIn(label=True, text='in concept')
    ]
    db.edit(namespace, concept_name, ConceptUpdate(insert=train_data))

    with pytest.raises(ValueError, match='Example with id "invalid_id" does not exist'):
      db.edit(namespace, concept_name, ConceptUpdate(remove=['invalid_id']))

  def test_edit_invalid_id(self, db_cls: Type[ConceptDB]) -> None:
    db = db_cls()
    namespace = 'test'
    concept_name = 'test_concept'
    train_data = [
        ExampleIn(label=False, text='not in concept'),
        ExampleIn(label=True, text='in concept')
    ]
    db.edit(namespace, concept_name, ConceptUpdate(insert=train_data))

    with pytest.raises(ValueError, match='Example with id "invalid_id" does not exist'):
      db.edit(namespace, concept_name,
              ConceptUpdate(update=[Example(id='invalid_id', label=False, text='not in concept')]))
