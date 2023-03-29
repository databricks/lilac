"""Test for the concept scorer."""

import os
from pathlib import Path
from typing import Generator, Iterable, Type, cast

import numpy as np
import pytest

from ..concepts.concept import ConceptModel, ExampleIn
from ..concepts.db_concept import (
    ConceptDB,
    ConceptModelDB,
    ConceptUpdate,
    DiskConceptDB,
    DiskConceptModelDB,
)
from ..embeddings.embedding_registry import clear_embedding_registry, register_embed_fn
from ..schema import RichData
from .concept_scorer import SCORE_FIELD_NAME, ConceptScoreSignal

ALL_CONCEPT_DBS = [DiskConceptDB]
ALL_CONCEPT_MODEL_DBS = [DiskConceptModelDB]


@pytest.fixture(autouse=True)
def set_data_path(tmp_path: Path) -> Generator:
  data_path = os.environ.get('LILAC_DATA_PATH', None)
  os.environ['LILAC_DATA_PATH'] = str(tmp_path)

  yield

  os.environ['LILAC_DATA_PATH'] = data_path or ''


@pytest.fixture(scope='module', autouse=True)
def setup_teardown() -> Generator:

  EMBEDDING_MAP: dict[str, list[float]] = {
      'not in concept': [1.0, 0.0, 0.0],
      'in concept': [0.9, 0.1, 0.0],
      'a new data point': [0.1, 0.2, 0.3],
  }

  @register_embed_fn('test_embedding')
  def embed(examples: Iterable[RichData]) -> np.ndarray:
    """Embed the examples, use a hashmap to the vector for simplicity."""
    for example in examples:
      if example not in EMBEDDING_MAP:
        raise ValueError(f'Example "{str(example)}" not in embedding map')
    return np.array([EMBEDDING_MAP[cast(str, example)] for example in examples])

  # Unit test runs.
  yield

  # Teardown.
  clear_embedding_registry()


@pytest.mark.parametrize('db_cls', ALL_CONCEPT_DBS)
def test_embedding_does_not_exist(db_cls: Type[ConceptDB]) -> None:
  db = db_cls()
  namespace = 'test'
  concept_name = 'test_concept'
  train_data = [
      ExampleIn(label=False, text='not in concept'),
      ExampleIn(label=True, text='in concept')
  ]
  db.edit(namespace, concept_name, ConceptUpdate(insert=train_data))

  with pytest.raises(ValueError, match='Embedding "unknown_embedding" not found in the registry'):
    ConceptScoreSignal(namespace='test',
                       concept_name='test_concept',
                       embedding_name='unknown_embedding')


def test_concept_model_does_not_exist() -> None:
  with pytest.raises(ValueError,
                     match='Concept model "test/test_concept/test_embedding" not found'):
    ConceptScoreSignal(namespace='test',
                       concept_name='test_concept',
                       embedding_name='test_embedding')


@pytest.mark.parametrize('db_cls', ALL_CONCEPT_DBS)
def test_concept_model_out_of_sync(db_cls: Type[ConceptDB]) -> None:
  db = db_cls()
  namespace = 'test'
  concept_name = 'test_concept'
  train_data = [
      ExampleIn(label=False, text='not in concept'),
      ExampleIn(label=True, text='in concept')
  ]
  db.edit(namespace, concept_name, ConceptUpdate(insert=train_data))

  with pytest.raises(ValueError,
                     match='Concept model "test/test_concept/test_embedding" is out of sync'):
    ConceptScoreSignal(namespace='test',
                       concept_name='test_concept',
                       embedding_name='test_embedding')


@pytest.mark.parametrize('concept_cls', ALL_CONCEPT_DBS)
@pytest.mark.parametrize('model_cls', ALL_CONCEPT_MODEL_DBS)
def test_concept_model_score(concept_cls: Type[ConceptDB], model_cls: Type[ConceptModelDB]) -> None:
  concept_db = concept_cls()
  model_db = model_cls(concept_db)
  namespace = 'test'
  concept_name = 'test_concept'
  train_data = [
      ExampleIn(label=False, text='not in concept'),
      ExampleIn(label=True, text='in concept')
  ]
  concept_db.edit(namespace, concept_name, ConceptUpdate(insert=train_data))

  concept_model = ConceptModel(namespace='test',
                               concept_name='test_concept',
                               embedding_name='test_embedding')
  model_db.save(concept_model)
  model_db.sync(concept_model)

  signal = ConceptScoreSignal(namespace='test',
                              concept_name='test_concept',
                              embedding_name='test_embedding')
  scores = signal.compute(data=['a new data point', 'not in concept'])
  expected_scores = [{SCORE_FIELD_NAME: 0.504}, {SCORE_FIELD_NAME: 0.493}]
  for score, expected_score in zip(scores, expected_scores):
    assert pytest.approx(expected_score, 1e-3) == score
