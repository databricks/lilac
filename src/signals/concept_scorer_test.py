"""Test for the concept scorer."""

import pathlib
from typing import Generator, Iterable, Type, cast

import numpy as np
import pytest
from typing_extensions import override

from ..concepts.concept import ConceptModelManager, ExampleIn
from ..concepts.db_concept import (
  ConceptDB,
  ConceptModelDB,
  ConceptUpdate,
  DiskConceptDB,
  DiskConceptModelDB,
)
from ..config import CONFIG
from ..embeddings.vector_store_numpy import NumpyVectorStore
from ..schema import RichData, SignalInputType, SignalOut
from .concept_scorer import ConceptScoreSignal
from .signal import TextEmbeddingSignal, clear_signal_registry, register_signal

ALL_CONCEPT_DBS = [DiskConceptDB]
ALL_CONCEPT_MODEL_DBS = [DiskConceptModelDB]


@pytest.fixture(autouse=True)
def set_data_path(tmp_path: pathlib.Path) -> Generator:
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
  # Setup.
  register_signal(TestEmbedding)

  # Unit test runs.
  yield

  # Teardown.
  clear_signal_registry()


@pytest.mark.parametrize('db_cls', ALL_CONCEPT_DBS)
def test_embedding_does_not_exist(db_cls: Type[ConceptDB]) -> None:
  db = db_cls()
  namespace = 'test'
  concept_name = 'test_concept'
  db.create(namespace=namespace, name=concept_name, type=SignalInputType.TEXT)

  train_data = [
    ExampleIn(label=False, text='not in concept'),
    ExampleIn(label=True, text='in concept')
  ]
  db.edit(namespace, concept_name, ConceptUpdate(insert=train_data))

  with pytest.raises(ValueError, match='Signal "unknown_embedding" not found in the registry'):
    ConceptScoreSignal(namespace='test', concept_name='test_concept', embedding='unknown_embedding')


def test_concept_does_not_exist() -> None:
  signal = ConceptScoreSignal(
    namespace='test', concept_name='test_concept', embedding='test_embedding')
  with pytest.raises(ValueError, match='Concept "test/test_concept" does not exist'):
    signal.compute(['a new data point', 'not in concept'])


@pytest.mark.parametrize('db_cls', ALL_CONCEPT_DBS)
def test_concept_model_out_of_sync(db_cls: Type[ConceptDB]) -> None:
  concept_db = db_cls()
  namespace = 'test'
  concept_name = 'test_concept'
  concept_db.create(namespace=namespace, name=concept_name, type=SignalInputType.TEXT)

  train_data = [
    ExampleIn(label=False, text='not in concept'),
    ExampleIn(label=True, text='in concept')
  ]
  concept_db.edit(namespace, concept_name, ConceptUpdate(insert=train_data))

  signal = ConceptScoreSignal(
    namespace='test', concept_name='test_concept', embedding='test_embedding')
  with pytest.raises(
      ValueError, match='Concept model "test/test_concept/test_embedding" is out of sync'):
    signal.compute(['a new data point', 'not in concept'])


@pytest.mark.parametrize('concept_db_cls', ALL_CONCEPT_DBS)
@pytest.mark.parametrize('model_db_cls', ALL_CONCEPT_MODEL_DBS)
def test_concept_model_score(concept_db_cls: Type[ConceptDB],
                             model_db_cls: Type[ConceptModelDB]) -> None:
  concept_db = concept_db_cls()
  model_db = model_db_cls(concept_db)
  namespace = 'test'
  concept_name = 'test_concept'
  concept_db.create(namespace=namespace, name=concept_name, type=SignalInputType.TEXT)

  train_data = [
    ExampleIn(label=False, text='not in concept'),
    ExampleIn(label=True, text='in concept')
  ]
  concept_db.edit(namespace, concept_name, ConceptUpdate(insert=train_data))

  signal = ConceptScoreSignal(
    namespace='test', concept_name='test_concept', embedding='test_embedding')

  # Explicitly sync the model with the concept.
  model_db.sync(
    ConceptModelManager(
      namespace='test', concept_name='test_concept', embedding_name='test_embedding'))

  scores = signal.compute(['a new data point', 'not in concept'])
  expected_scores = [0.801, 0.465]
  for score, expected_score in zip(scores, expected_scores):
    assert pytest.approx(expected_score, 1e-3) == score


@pytest.mark.parametrize('concept_db_cls', ALL_CONCEPT_DBS)
@pytest.mark.parametrize('model_db_cls', ALL_CONCEPT_MODEL_DBS)
def test_concept_model_vector_score(concept_db_cls: Type[ConceptDB],
                                    model_db_cls: Type[ConceptModelDB]) -> None:
  concept_db = concept_db_cls()
  model_db = model_db_cls(concept_db)
  namespace = 'test'
  concept_name = 'test_concept'
  concept_db.create(namespace=namespace, name=concept_name, type=SignalInputType.TEXT)

  train_data = [
    ExampleIn(label=False, text='not in concept'),
    ExampleIn(label=True, text='in concept')
  ]
  concept_db.edit(namespace, concept_name, ConceptUpdate(insert=train_data))

  signal = ConceptScoreSignal(
    namespace='test', concept_name='test_concept', embedding='test_embedding')

  # Explicitly sync the model with the concept.
  model_db.sync(
    ConceptModelManager(
      namespace='test', concept_name='test_concept', embedding_name='test_embedding'))

  vector_store = NumpyVectorStore()
  vector_store.add([('1',), ('2',), ('3',)],
                   np.array([[1.0, 0.0, 0.0], [0.9, 0.1, 0.0], [0.1, 0.2, 0.3]]))

  scores = signal.vector_compute([('1',), ('2',), ('3',)], vector_store)

  expected_scores = [0.465, 0.535, 0.801]
  for score, expected_score in zip(scores, expected_scores):
    assert pytest.approx(expected_score, 1e-3) == score


@pytest.mark.parametrize('concept_db_cls', ALL_CONCEPT_DBS)
@pytest.mark.parametrize('model_db_cls', ALL_CONCEPT_MODEL_DBS)
def test_concept_model_topk_score(concept_db_cls: Type[ConceptDB],
                                  model_db_cls: Type[ConceptModelDB]) -> None:
  concept_db = concept_db_cls()
  model_db = model_db_cls(concept_db)
  namespace = 'test'
  concept_name = 'test_concept'
  concept_db.create(namespace=namespace, name=concept_name, type=SignalInputType.TEXT)

  train_data = [
    ExampleIn(label=False, text='not in concept'),
    ExampleIn(label=True, text='in concept')
  ]
  concept_db.edit(namespace, concept_name, ConceptUpdate(insert=train_data))

  signal = ConceptScoreSignal(
    namespace='test', concept_name='test_concept', embedding='test_embedding')

  # Explicitly sync the model with the concept.
  model_db.sync(
    ConceptModelManager(
      namespace='test', concept_name='test_concept', embedding_name='test_embedding'))
  vector_store = NumpyVectorStore()
  vector_store.add([('1',), ('2',), ('3',)],
                   np.array([[1.0, 0.0, 0.0], [0.9, 0.1, 0.0], [0.1, 0.2, 0.3]]))

  # Compute topk without id restriction.
  topk_result = signal.vector_compute_topk(3, vector_store)
  expected_result = [(('3',), 0.801), (('2',), 0.535), (('1',), 0.465)]
  for (id, score), (expected_id, expected_score) in zip(topk_result, expected_result):
    assert id == expected_id
    assert score == pytest.approx(expected_score, 1e-3)

  # Compute top 1.
  topk_result = signal.vector_compute_topk(1, vector_store)
  expected_result = [(('3',), 0.801)]
  for (id, score), (expected_id, expected_score) in zip(topk_result, expected_result):
    assert id == expected_id
    assert score == pytest.approx(expected_score, 1e-3)

  # Compute topk with id restriction.
  topk_result = signal.vector_compute_topk(3, vector_store, keys=[('1',), ('2',)])
  expected_result = [(('2',), 0.535), (('1',), 0.465)]
  for (id, score), (expected_id, expected_score) in zip(topk_result, expected_result):
    assert id == expected_id
    assert score == pytest.approx(expected_score, 1e-3)


@pytest.mark.parametrize('concept_db_cls', ALL_CONCEPT_DBS)
@pytest.mark.parametrize('model_db_cls', ALL_CONCEPT_MODEL_DBS)
def test_concept_model_draft(concept_db_cls: Type[ConceptDB],
                             model_db_cls: Type[ConceptModelDB]) -> None:
  concept_db = concept_db_cls()
  model_db = model_db_cls(concept_db)
  namespace = 'test'
  concept_name = 'test_concept'
  concept_db.create(namespace=namespace, name=concept_name, type=SignalInputType.TEXT)

  train_data = [
    ExampleIn(label=False, text='not in concept'),
    ExampleIn(label=True, text='in concept'),
    ExampleIn(label=False, text='a new data point', draft='test_draft'),
  ]
  concept_db.edit(namespace, concept_name, ConceptUpdate(insert=train_data))

  signal = ConceptScoreSignal(
    namespace='test', concept_name='test_concept', embedding='test_embedding')
  draft_signal = ConceptScoreSignal(
    namespace='test', concept_name='test_concept', embedding='test_embedding', draft='test_draft')

  # Explicitly sync the model with the concept.
  model_db.sync(
    ConceptModelManager(
      namespace='test', concept_name='test_concept', embedding_name='test_embedding'))

  vector_store = NumpyVectorStore()
  vector_store.add([('1',), ('2',), ('3',)],
                   np.array([[1.0, 0.0, 0.0], [0.9, 0.1, 0.0], [0.1, 0.2, 0.3]]))

  scores = signal.vector_compute([('1',), ('2',), ('3',)], vector_store)

  expected_scores = [0.465, 0.535, 0.801]
  for score, expected_score in zip(scores, expected_scores):
    assert pytest.approx(expected_score, 1e-3) == score

  # Make sure the draft signal works. It has different values than the original signal.
  vector_store = NumpyVectorStore()
  vector_store.add([('1',), ('2',), ('3',)],
                   np.array([[1.0, 0.0, 0.0], [0.9, 0.1, 0.0], [0.1, 0.2, 0.3]]))

  scores = draft_signal.vector_compute([('1',), ('2',), ('3',)], vector_store)

  expected_scores = [0.620, 0.596, 0.187]
  for score, expected_score in zip(scores, expected_scores):
    assert pytest.approx(expected_score, 1e-3) == score


def test_concept_score_key() -> None:
  signal = ConceptScoreSignal(
    namespace='test', concept_name='test_concept', embedding=TestEmbedding.name)
  assert signal.key() == 'test/test_concept'
