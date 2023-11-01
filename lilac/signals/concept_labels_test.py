"""Test for the concept label signal."""

import os
import pathlib
from typing import Generator, Type

import pytest
from pytest_mock import MockerFixture

from ..concepts.concept import ExampleIn
from ..concepts.db_concept import ConceptDB, ConceptUpdate, DiskConceptDB, DiskConceptModelDB
from ..data.dataset_duckdb import DatasetDuckDB
from ..db_manager import set_default_dataset_cls
from ..schema import SignalInputType, lilac_span
from ..signal import clear_signal_registry
from .concept_labels import ConceptLabelsSignal

ALL_CONCEPT_DBS = [DiskConceptDB]
ALL_CONCEPT_MODEL_DBS = [DiskConceptModelDB]


@pytest.fixture(autouse=True)
def set_project_dir(tmp_path: pathlib.Path, mocker: MockerFixture) -> None:
  mocker.patch.dict(os.environ, {'LILAC_PROJECT_DIR': str(tmp_path)})


@pytest.fixture(scope='module', autouse=True)
def setup_teardown() -> Generator:
  # Setup.
  set_default_dataset_cls(DatasetDuckDB)

  # Unit test runs.
  yield

  # Teardown.
  clear_signal_registry()


def test_concept_does_not_exist() -> None:
  signal = ConceptLabelsSignal(namespace='test', concept_name='concept_doesnt_exist')
  with pytest.raises(ValueError, match='Concept "test/concept_doesnt_exist" does not exist'):
    list(signal.compute(['a new data point', 'not in concept']))


@pytest.mark.parametrize('concept_db_cls', ALL_CONCEPT_DBS)
def test_concept_labels(concept_db_cls: Type[ConceptDB]) -> None:
  concept_db = concept_db_cls()
  namespace = 'test'
  concept_name = 'test_concept'
  concept_db.create(namespace=namespace, name=concept_name, type=SignalInputType.TEXT)

  train_data = [
    ExampleIn(label=False, text='no in concept'),
    ExampleIn(label=True, text='yes in concept'),
    # This should never show since we request the main draft.
    ExampleIn(label=False, text='this is unrelated', draft='test_draft'),
  ]
  concept_db.edit(namespace, concept_name, ConceptUpdate(insert=train_data))

  signal = ConceptLabelsSignal(namespace='test', concept_name='test_concept')
  results = list(
    signal.compute(
      [
        'this is no in concept',
        'this is yes in concept',
        'this is no in concept. filler. this is yes in concept.',
        'this is unrelated',
      ]
    )
  )

  assert results == [
    [lilac_span(8, 8 + len('no in concept'), {'label': False})],
    [lilac_span(8, 8 + len('yes in concept'), {'label': True})],
    [
      lilac_span(8, 8 + len('no in concept'), {'label': False}),
      lilac_span(39, 39 + len('yes in concept'), {'label': True}),
    ],
    # This example is in the draft, which was not requested.
    None,
  ]


@pytest.mark.parametrize('concept_db_cls', ALL_CONCEPT_DBS)
def test_concept_labels_draft(concept_db_cls: Type[ConceptDB]) -> None:
  concept_db = concept_db_cls()
  namespace = 'test'
  concept_name = 'test_concept'
  concept_db.create(namespace=namespace, name=concept_name, type=SignalInputType.TEXT)

  concept_update = ConceptUpdate(
    insert=[
      ExampleIn(label=True, text='in concept'),
      ExampleIn(label=False, text='out of concept'),
      ExampleIn(label=True, text='in draft', draft='test_draft'),
      ExampleIn(label=False, text='out draft', draft='test_draft'),
    ]
  )

  concept_db.edit(namespace, concept_name, concept_update)

  signal = ConceptLabelsSignal(namespace='test', concept_name='test_concept', draft='test_draft')
  results = list(signal.compute(['this is in concept', 'this is in draft', 'this is out draft']))

  assert results == [
    [lilac_span(8, 8 + len('in concept'), {'label': True})],
    [lilac_span(8, 8 + len('in draft'), {'label': True, 'draft': 'test_draft'})],
    [lilac_span(8, 8 + len('out draft'), {'label': False, 'draft': 'test_draft'})],
  ]


@pytest.mark.parametrize('concept_db_cls', ALL_CONCEPT_DBS)
def test_concept_labels_key(concept_db_cls: Type[ConceptDB]) -> None:
  concept_db = concept_db_cls()
  namespace = 'test'
  concept_name = 'test_concept'
  concept_db.create(namespace=namespace, name=concept_name, type=SignalInputType.TEXT)

  signal = ConceptLabelsSignal(namespace='test', concept_name='test_concept')
  assert signal.key() == 'test/test_concept/labels/preview'


@pytest.mark.parametrize('concept_db_cls', ALL_CONCEPT_DBS)
def test_concept_labels_compute_signal_key(concept_db_cls: Type[ConceptDB]) -> None:
  concept_db = concept_db_cls()
  namespace = 'test'
  concept_name = 'test_concept'
  concept_db.create(namespace=namespace, name=concept_name, type=SignalInputType.TEXT)

  signal = ConceptLabelsSignal(namespace='test', concept_name='test_concept')
  assert signal.key(is_computed_signal=True) == 'test/test_concept/labels'
