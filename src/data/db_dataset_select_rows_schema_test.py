"""Tests for `db.select_rows_schema()`."""

import pathlib
from typing import Generator, Iterable, Optional, Type, cast

import numpy as np
import pytest
from typing_extensions import override

from ..config import CONFIG
from ..embeddings.embedding import EmbeddingSignal
from ..embeddings.vector_store import VectorStore
from ..schema import (
  LILAC_COLUMN,
  UUID_COLUMN,
  DataType,
  EnrichmentType,
  Field,
  Item,
  ItemValue,
  PathTuple,
  RichData,
  SignalOut,
  field,
  schema,
  signal_field,
)
from ..signals.signal import Signal
from ..signals.signal_registry import clear_signal_registry, register_signal
from .dataset_utils import signal_item
from .db_dataset import DatasetDB, SignalUDF
from .db_dataset_duckdb import DatasetDuckDB
from .db_dataset_test_utils import make_db

ALL_DBS = [DatasetDuckDB]

SIMPLE_DATASET_NAME = 'simple'

TEST_DATA: list[Item] = [{
  UUID_COLUMN: '1',
  'erased': False,
  'people': [{
    'name': 'A',
    'zipcode': 0,
    'locations': [{
      'city': 'city1',
      'state': 'state1'
    }, {
      'city': 'city2',
      'state': 'state2'
    }]
  }]
}, {
  UUID_COLUMN: '2',
  'erased': True,
  'people': [{
    'name': 'B',
    'zipcode': 1,
    'locations': [{
      'city': 'city3',
      'state': 'state3'
    }, {
      'city': 'city4'
    }, {
      'city': 'city5'
    }]
  }, {
    'name': 'C',
    'zipcode': 2,
    'locations': [{
      'city': 'city1',
      'state': 'state1'
    }]
  }]
}]

EMBEDDINGS: list[tuple[str, list[float]]] = [
  ('A', [1.0, 0.0, 0.0]),
  ('B', [1.0, 1.0, 0.0]),
  ('C', [1.0, 1.0, 1.0]),
]

STR_EMBEDDINGS: dict[str, list[float]] = {text: embedding for text, embedding in EMBEDDINGS}


class TestEmbedding(EmbeddingSignal):
  """A test embed function."""
  name = 'test_embedding'
  enrichment_type = EnrichmentType.TEXT

  @override
  def fields(self) -> Field:
    """Return the fields for the embedding."""
    # Override in the test so we can attach extra metadata.
    return Field(dtype=DataType.EMBEDDING)

  @override
  def compute(self, data: Iterable[RichData]) -> Iterable[Item]:
    """Call the embedding function."""
    embeddings = [np.array(STR_EMBEDDINGS[cast(str, example)]) for example in data]
    yield from (signal_item(e, metadata={'neg_sum': -1 * e.sum()}) for e in embeddings)


class TestEmbeddingSumSignal(Signal):
  """Sums the embeddings to return a single floating point value."""
  name = 'test_embedding_sum'
  enrichment_type = EnrichmentType.TEXT_EMBEDDING

  @override
  def fields(self) -> Field:
    return field('float32')

  @override
  def vector_compute(self, keys: Iterable[PathTuple],
                     vector_store: VectorStore) -> Iterable[ItemValue]:
    # The signal just sums the values of the embedding.
    embedding_sums = vector_store.get(keys).sum(axis=1)
    for embedding_sum in embedding_sums.tolist():
      yield embedding_sum


@pytest.fixture(autouse=True)
def set_data_path(tmp_path: pathlib.Path) -> Generator:
  data_path = CONFIG['LILAC_DATA_PATH']
  CONFIG['LILAC_DATA_PATH'] = str(tmp_path)
  yield
  CONFIG['LILAC_DATA_PATH'] = data_path or ''


@pytest.fixture(scope='module', autouse=True)
def setup_teardown() -> Iterable[None]:
  # Setup.
  register_signal(TestEmbedding)
  register_signal(TestEmbeddingSumSignal)

  # Unit test runs.
  yield

  # Teardown.
  clear_signal_registry()


class LengthSignal(Signal):
  name = 'length_signal'
  enrichment_type = EnrichmentType.TEXT

  def fields(self) -> Field:
    return field('int32')

  def compute(self, data: Iterable[RichData]) -> Iterable[Optional[SignalOut]]:
    for text_content in data:
      yield len(text_content)


@pytest.mark.parametrize('db_cls', ALL_DBS)
class SelectRowsSchemaSuite:

  def test_simple_schema(self, tmp_path: pathlib.Path, db_cls: Type[DatasetDB]) -> None:
    db = make_db(db_cls, tmp_path, TEST_DATA)
    result = db.select_rows_schema(combine_columns=True)
    assert result == schema({
      UUID_COLUMN: 'string',
      'erased': 'boolean',
      'people': [{
        'name': 'string',
        'zipcode': 'int32',
        'locations': [{
          'city': 'string',
          'state': 'string'
        }]
      }]
    })

  def test_subselection_with_combine_cols(self, tmp_path: pathlib.Path,
                                          db_cls: Type[DatasetDB]) -> None:
    db = make_db(db_cls, tmp_path, TEST_DATA)

    result = db.select_rows_schema([('people', '*', 'zipcode'),
                                    ('people', '*', 'locations', '*', 'city')],
                                   combine_columns=True)
    assert result == schema({
      UUID_COLUMN: 'string',
      'people': [{
        'zipcode': 'int32',
        'locations': [{
          'city': 'string'
        }]
      }]
    })

    result = db.select_rows_schema([('people', '*', 'name'), ('people', '*', 'locations')],
                                   combine_columns=True)
    assert result == schema({
      UUID_COLUMN: 'string',
      'people': [{
        'name': 'string',
        'locations': [{
          'city': 'string',
          'state': 'string'
        }]
      }]
    })

    result = db.select_rows_schema([('people', '*')], combine_columns=True)
    assert result == schema({
      UUID_COLUMN: 'string',
      'people': [{
        'name': 'string',
        'zipcode': 'int32',
        'locations': [{
          'city': 'string',
          'state': 'string'
        }]
      }]
    })

  def test_udf_with_combine_cols(self, tmp_path: pathlib.Path, db_cls: Type[DatasetDB]) -> None:
    db = make_db(db_cls, tmp_path, TEST_DATA)

    result = db.select_rows_schema([('people', '*', 'locations', '*', 'city'),
                                    SignalUDF(LengthSignal(), ('people', '*', 'name'))],
                                   combine_columns=True)
    assert result == schema({
      UUID_COLUMN: 'string',
      'people': [{
        'locations': [{
          'city': 'string'
        }]
      }],
      LILAC_COLUMN: {
        'people': [{
          'name': {
            'length_signal': signal_field(dtype='int32')
          }
        }]
      }
    })

  def test_embedding_udf_with_combine_cols(self, tmp_path: pathlib.Path,
                                           db_cls: Type[DatasetDB]) -> None:
    db = make_db(db_cls, tmp_path, TEST_DATA)

    db.compute_signal(TestEmbedding(), ('people', '*', 'name'))
    result = db.select_rows_schema(
      [('people', '*', 'locations', '*', 'city'),
       SignalUDF(TestEmbeddingSumSignal(),
                 (LILAC_COLUMN, 'people', '*', 'name', 'test_embedding'))],
      combine_columns=True)
    assert result == schema({
      UUID_COLUMN: 'string',
      'people': [{
        'locations': [{
          'city': 'string'
        }]
      }],
      LILAC_COLUMN: {
        'people': [{
          'name': {
            'test_embedding': {
              'test_embedding_sum': signal_field(dtype='float32')
            }
          }
        }]
      }
    })
