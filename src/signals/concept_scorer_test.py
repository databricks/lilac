"""Test for the concept scorer."""

import os
import pathlib
from typing import Generator, Iterable, Type, cast

import numpy as np
import pytest
from typing_extensions import override

from ..concepts.concept import ConceptModel, ExampleIn
from ..concepts.db_concept import (
    ConceptDB,
    ConceptModelDB,
    ConceptUpdate,
    DiskConceptDB,
    DiskConceptModelDB,
)
from ..embeddings.embedding_index import EmbeddingIndex
from ..embeddings.embedding_registry import Embedding, clear_embedding_registry, register_embedding
from ..schema import EnrichmentType, RichData
from .concept_scorer import ConceptScoreSignal

ALL_CONCEPT_DBS = [DiskConceptDB]
ALL_CONCEPT_MODEL_DBS = [DiskConceptModelDB]


@pytest.fixture(autouse=True)
def set_data_path(tmp_path: pathlib.Path) -> Generator:
  data_path = os.environ.get('LILAC_DATA_PATH', None)
  os.environ['LILAC_DATA_PATH'] = str(tmp_path)

  yield

  os.environ['LILAC_DATA_PATH'] = data_path or ''


EMBEDDING_MAP: dict[str, list[float]] = {
    'not in concept': [1.0, 0.0, 0.0],
    'in concept': [0.9, 0.1, 0.0],
    'a new data point': [0.1, 0.2, 0.3],
}


class TestEmbedding(Embedding):
  """A test embed function."""
  name = 'test_embedding'
  enrichment_type = EnrichmentType.TEXT

  @override
  def __call__(self, examples: Iterable[RichData]) -> np.ndarray:
    """Embed the examples, use a hashmap to the vector for simplicity."""
    for example in examples:
      if example not in EMBEDDING_MAP:
        raise ValueError(f'Example "{str(example)}" not in embedding map')
    return np.array([EMBEDDING_MAP[cast(str, example)] for example in examples])


@pytest.fixture(scope='module', autouse=True)
def setup_teardown() -> Generator:
  # Setup.
  register_embedding(TestEmbedding)

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


def test_concept_does_not_exist() -> None:
  signal = ConceptScoreSignal(namespace='test',
                              concept_name='test_concept',
                              embedding_name='test_embedding')
  with pytest.raises(ValueError, match='Concept "test/test_concept" does not exist'):
    signal.compute(data=['a new data point', 'not in concept'])


@pytest.mark.parametrize('db_cls', ALL_CONCEPT_DBS)
def test_concept_model_out_of_sync(db_cls: Type[ConceptDB]) -> None:
  concept_db = db_cls()
  namespace = 'test'
  concept_name = 'test_concept'
  train_data = [
      ExampleIn(label=False, text='not in concept'),
      ExampleIn(label=True, text='in concept')
  ]
  concept_db.edit(namespace, concept_name, ConceptUpdate(insert=train_data))

  signal = ConceptScoreSignal(namespace='test',
                              concept_name='test_concept',
                              embedding_name='test_embedding')
  with pytest.raises(ValueError,
                     match='Concept model "test/test_concept/test_embedding" is out of sync'):
    signal.compute(data=['a new data point', 'not in concept'])


@pytest.mark.parametrize('concept_db_cls', ALL_CONCEPT_DBS)
@pytest.mark.parametrize('model_db_cls', ALL_CONCEPT_MODEL_DBS)
def test_concept_model_score(concept_db_cls: Type[ConceptDB],
                             model_db_cls: Type[ConceptModelDB]) -> None:
  concept_db = concept_db_cls()
  model_db = model_db_cls(concept_db)
  namespace = 'test'
  concept_name = 'test_concept'
  train_data = [
      ExampleIn(label=False, text='not in concept'),
      ExampleIn(label=True, text='in concept')
  ]
  concept_db.edit(namespace, concept_name, ConceptUpdate(insert=train_data))

  signal = ConceptScoreSignal(namespace='test',
                              concept_name='test_concept',
                              embedding_name='test_embedding')

  # Explicitly sync the model with the concept.
  model_db.sync(
      ConceptModel(namespace='test', concept_name='test_concept', embedding_name='test_embedding'))

  scores = signal.compute(data=['a new data point', 'not in concept'])
  expected_scores = [0.504, 0.493]
  for score, expected_score in zip(scores, expected_scores):
    assert pytest.approx(expected_score, 1e-3) == score


@pytest.mark.parametrize('concept_db_cls', ALL_CONCEPT_DBS)
@pytest.mark.parametrize('model_db_cls', ALL_CONCEPT_MODEL_DBS)
def test_concept_model_score_embeddings(concept_db_cls: Type[ConceptDB],
                                        model_db_cls: Type[ConceptModelDB]) -> None:
  concept_db = concept_db_cls()
  model_db = model_db_cls(concept_db)
  namespace = 'test'
  concept_name = 'test_concept'
  train_data = [
      ExampleIn(label=False, text='not in concept'),
      ExampleIn(label=True, text='in concept')
  ]
  concept_db.edit(namespace, concept_name, ConceptUpdate(insert=train_data))

  signal = ConceptScoreSignal(namespace='test',
                              concept_name='test_concept',
                              embedding_name='test_embedding')

  # Explicitly sync the model with the concept.
  model_db.sync(
      ConceptModel(namespace='test', concept_name='test_concept', embedding_name='test_embedding'))

  KEY_EMBEDDING_MAP: dict[str, list[float]] = {
      '1': [1.0, 0.0, 0.0],
      '2': [0.9, 0.1, 0.0],
      '3': [0.1, 0.2, 0.3],
  }

  scores = signal.compute(keys=['1', '2', '3'],
                          get_embedding_index=lambda _, row_ids: EmbeddingIndex(embeddings=np.array(
                              [KEY_EMBEDDING_MAP[x] for x in row_ids])))

  expected_scores = [0.493, 0.495, 0.504]
  for score, expected_score in zip(scores, expected_scores):
    assert pytest.approx(expected_score, 1e-3) == score
