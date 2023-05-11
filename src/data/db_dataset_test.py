"""Implementation-agnostic tests of the Dataset DB API."""

import pathlib
from typing import Generator, Iterable, Optional, Type, cast

import numpy as np
import pytest
from typing_extensions import override

from ..config import CONFIG
from ..embeddings.embedding import EmbeddingSignal
from ..embeddings.vector_store import VectorStore
from ..schema import (
  SIGNAL_METADATA_KEY,
  UUID_COLUMN,
  VALUE_KEY,
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
from .dataset_utils import lilac_item, lilac_items, signal_item
from .db_dataset import (
  Column,
  Comparison,
  DatasetDB,
  DatasetManifest,
  FilterTuple,
  SignalUDF,
  SortOrder,
  val,
)
from .db_dataset_duckdb import DatasetDuckDB
from .db_dataset_test_utils import TEST_DATASET_NAME, TEST_NAMESPACE, make_db

ALL_DBS = [DatasetDuckDB]

SIMPLE_ITEMS: list[Item] = [{
  UUID_COLUMN: '1',
  'str': 'a',
  'int': 1,
  'bool': False,
  'float': 3.0
}, {
  UUID_COLUMN: '2',
  'str': 'b',
  'int': 2,
  'bool': True,
  'float': 2.0
}, {
  UUID_COLUMN: '3',
  'str': 'b',
  'int': 2,
  'bool': True,
  'float': 1.0
}]

TEST_EMBEDDING_NAME = 'test_embedding'

EMBEDDINGS: list[tuple[str, list[float]]] = [('hello.', [1.0, 0.0, 0.0]),
                                             ('hello2.', [1.0, 1.0, 0.0]),
                                             ('hello world.', [1.0, 1.0, 1.0]),
                                             ('hello world2.', [2.0, 1.0, 1.0])]

STR_EMBEDDINGS: dict[str, list[float]] = {text: embedding for text, embedding in EMBEDDINGS}


class TestEmbedding(EmbeddingSignal):
  """A test embed function."""
  name = TEST_EMBEDDING_NAME
  enrichment_type = EnrichmentType.TEXT

  @override
  def fields(self) -> Field:
    """Return the fields for the embedding."""
    # Override in the test so we can attach extra metadata.
    return Field(
      dtype=DataType.EMBEDDING, fields={SIGNAL_METADATA_KEY: field({'neg_sum': 'float32'})})

  @override
  def compute(self, data: Iterable[RichData]) -> Iterable[Item]:
    """Call the embedding function."""
    embeddings = [np.array(STR_EMBEDDINGS[cast(str, example)]) for example in data]
    yield from (signal_item(e, metadata={'neg_sum': -1 * e.sum()}) for e in embeddings)


class LengthSignal(Signal):
  name = 'length_signal'
  enrichment_type = EnrichmentType.TEXT

  _call_count: int = 0

  def fields(self) -> Field:
    return field('int32')

  def compute(self, data: Iterable[RichData]) -> Iterable[Optional[SignalOut]]:
    for text_content in data:
      self._call_count += 1
      yield len(text_content)


@pytest.fixture(scope='module', autouse=True)
def setup_teardown() -> Iterable[None]:
  # Setup.
  register_signal(TestSignal)
  register_signal(LengthSignal)
  register_signal(TestEmbeddingSumSignal)
  register_signal(TestEmbedding)

  # Unit test runs.
  yield

  # Teardown.
  clear_signal_registry()


@pytest.fixture(autouse=True)
def set_data_path(tmp_path: pathlib.Path) -> Generator:
  data_path = CONFIG['LILAC_DATA_PATH']
  CONFIG['LILAC_DATA_PATH'] = str(tmp_path)

  yield

  CONFIG['LILAC_DATA_PATH'] = data_path or ''


@pytest.mark.parametrize('db_cls', ALL_DBS)
class SelectRowsSuite:

  def test_default(self, tmp_path: pathlib.Path, db_cls: Type[DatasetDB]) -> None:
    db = make_db(db_cls, tmp_path, SIMPLE_ITEMS)

    result = db.select_rows()
    assert list(result) == lilac_items(SIMPLE_ITEMS)

  def test_select_ids(self, tmp_path: pathlib.Path, db_cls: Type[DatasetDB]) -> None:
    db = make_db(db_cls, tmp_path, SIMPLE_ITEMS)

    result = db.select_rows([UUID_COLUMN])

    assert list(result) == [{UUID_COLUMN: '1'}, {UUID_COLUMN: '2'}, {UUID_COLUMN: '3'}]

  def test_select_ids_with_limit_and_offset(self, tmp_path: pathlib.Path,
                                            db_cls: Type[DatasetDB]) -> None:
    items: list[Item] = [{UUID_COLUMN: str(i)} for i in range(10, 20)]
    db = make_db(db_cls, tmp_path, items)

    result = db.select_rows([UUID_COLUMN], offset=1, limit=3)
    assert list(result) == [{UUID_COLUMN: '11'}, {UUID_COLUMN: '12'}, {UUID_COLUMN: '13'}]

    result = db.select_rows([UUID_COLUMN], offset=7, limit=2)
    assert list(result) == [{UUID_COLUMN: '17'}, {UUID_COLUMN: '18'}]

    result = db.select_rows([UUID_COLUMN], offset=9, limit=200)
    assert list(result) == [{UUID_COLUMN: '19'}]

    result = db.select_rows([UUID_COLUMN], offset=10, limit=200)
    assert list(result) == []

  def test_filter_by_ids(self, tmp_path: pathlib.Path, db_cls: Type[DatasetDB]) -> None:
    db = make_db(db_cls, tmp_path, SIMPLE_ITEMS)

    id_filter: FilterTuple = (UUID_COLUMN, Comparison.EQUALS, '1')
    result = db.select_rows(filters=[id_filter])

    assert list(result) == lilac_items([{
      UUID_COLUMN: '1',
      'str': 'a',
      'int': 1,
      'bool': False,
      'float': 3.0
    }])

    id_filter = (UUID_COLUMN, Comparison.EQUALS, '2')
    result = db.select_rows(filters=[id_filter])

    assert list(result) == lilac_items([{
      UUID_COLUMN: '2',
      'str': 'b',
      'int': 2,
      'bool': True,
      'float': 2.0
    }])

    id_filter = (UUID_COLUMN, Comparison.EQUALS, b'f')
    result = db.select_rows(filters=[id_filter])

    assert list(result) == []

  def test_filter_by_list_of_ids(self, tmp_path: pathlib.Path, db_cls: Type[DatasetDB]) -> None:
    db = make_db(db_cls, tmp_path, SIMPLE_ITEMS)

    id_filter: FilterTuple = (UUID_COLUMN, Comparison.IN, ['1', '2'])
    result = db.select_rows(filters=[id_filter])

    assert list(result) == lilac_items([{
      UUID_COLUMN: '1',
      'str': 'a',
      'int': 1,
      'bool': False,
      'float': 3.0
    }, {
      UUID_COLUMN: '2',
      'str': 'b',
      'int': 2,
      'bool': True,
      'float': 2.0
    }])

  def test_columns(self, tmp_path: pathlib.Path, db_cls: Type[DatasetDB]) -> None:
    db = make_db(db_cls, tmp_path, SIMPLE_ITEMS)

    result = db.select_rows(['str', 'float'])

    assert list(result) == lilac_items([{
      UUID_COLUMN: '1',
      'str': 'a',
      'float': 3.0
    }, {
      UUID_COLUMN: '2',
      'str': 'b',
      'float': 2.0
    }, {
      UUID_COLUMN: '3',
      'str': 'b',
      'float': 1.0
    }])

  def test_merge_values(self, tmp_path: pathlib.Path, db_cls: Type[DatasetDB]) -> None:
    db = make_db(
      db_cls,
      tmp_path,
      items=[{
        UUID_COLUMN: '1',
        'text': 'hello'
      }, {
        UUID_COLUMN: '2',
        'text': 'everybody'
      }])
    test_signal = TestSignal()
    db.compute_signal(test_signal, 'text')
    length_signal = LengthSignal()
    db.compute_signal(length_signal, 'text')

    result = db.select_rows(['text'])
    assert list(result) == lilac_items([{
      UUID_COLUMN: '1',
      'text': lilac_item('hello', {
        'length_signal': 5,
        'test_signal': {
          'len': 5,
          'flen': 5.0
        }
      })
    }, {
      UUID_COLUMN: '2',
      'text': lilac_item('everybody', {
        'length_signal': 9,
        'test_signal': {
          'len': 9,
          'flen': 9.0
        }
      }),
    }])

    # Test subselection.
    result = db.select_rows(
      [val('text'), ('text', 'test_signal', 'flen'), ('text', 'test_signal', 'len')])
    assert list(result) == [{
      UUID_COLUMN: '1',
      f'text.{VALUE_KEY}': 'hello',
      'text.test_signal.flen': lilac_item(5.0),
      'text.test_signal.len': lilac_item(5)
    }, {
      UUID_COLUMN: '2',
      f'text.{VALUE_KEY}': 'everybody',
      'text.test_signal.flen': lilac_item(9.0),
      'text.test_signal.len': lilac_item(9)
    }]

    # Test subselection with combine_columns=True.
    result = db.select_rows(
      ['text', ('text', 'test_signal', 'flen'), ('text', 'test_signal', 'len')],
      combine_columns=True)
    assert list(result) == lilac_items([{
      UUID_COLUMN: '1',
      'text': lilac_item('hello', {
        'length_signal': 5,
        'test_signal': {
          'len': 5,
          'flen': 5.0
        }
      })
    }, {
      UUID_COLUMN: '2',
      'text': lilac_item('everybody', {
        'length_signal': 9,
        'test_signal': {
          'len': 9,
          'flen': 9.0
        }
      }),
    }])

    # Test subselection with aliasing.
    result = db.select_rows(
      columns=[val('text'), Column(('text', 'test_signal', 'len'), alias='metadata')])
    assert list(result) == [{
      UUID_COLUMN: '1',
      f'text.{VALUE_KEY}': 'hello',
      'metadata': lilac_item(5)
    }, {
      UUID_COLUMN: '2',
      f'text.{VALUE_KEY}': 'everybody',
      'metadata': lilac_item(9)
    }]

    result = db.select_rows(columns=[Column(('text'), alias='text_enrichment')])
    assert list(result) == lilac_items([{
      UUID_COLUMN: '1',
      'text_enrichment': lilac_item('hello', {
        'length_signal': 5,
        'test_signal': {
          'len': 5,
          'flen': 5.0
        }
      })
    }, {
      UUID_COLUMN: '2',
      'text_enrichment': lilac_item('everybody', {
        'length_signal': 9,
        'test_signal': {
          'len': 9,
          'flen': 9.0
        }
      })
    }])

  def test_merge_array_values(self, tmp_path: pathlib.Path, db_cls: Type[DatasetDB]) -> None:
    db = make_db(
      db_cls,
      tmp_path,
      items=[{
        UUID_COLUMN: '1',
        'texts': ['hello', 'everybody']
      }, {
        UUID_COLUMN: '2',
        'texts': ['a', 'bc', 'def']
      }])

    db.compute_signal(TestSignal(), ('texts', '*'))
    db.compute_signal(LengthSignal(), ('texts', '*'))

    assert db.manifest() == DatasetManifest(
      namespace=TEST_NAMESPACE,
      dataset_name=TEST_DATASET_NAME,
      data_schema=schema({
        UUID_COLUMN: 'string',
        'texts': [
          field(
            {
              'length_signal': signal_field('int32'),
              'test_signal': signal_field({
                'len': 'int32',
                'flen': 'float32'
              })
            },
            dtype='string')
        ],
      }),
      num_items=2)

    result = db.select_rows(['texts'])
    assert list(result) == lilac_items([{
      UUID_COLUMN: '1',
      'texts': [
        lilac_item('hello', {
          'length_signal': 5,
          'test_signal': {
            'len': 5,
            'flen': 5.0
          }
        }),
        lilac_item('everybody', {
          'length_signal': 9,
          'test_signal': {
            'len': 9,
            'flen': 9.0
          }
        })
      ],
    }, {
      UUID_COLUMN: '2',
      'texts': [
        lilac_item('a', {
          'length_signal': 1,
          'test_signal': {
            'len': 1,
            'flen': 1.0
          }
        }),
        lilac_item('bc', {
          'length_signal': 2,
          'test_signal': {
            'len': 2,
            'flen': 2.0
          }
        }),
        lilac_item('def', {
          'length_signal': 3,
          'test_signal': {
            'len': 3,
            'flen': 3.0
          }
        })
      ],
    }])

    # Test subselection.
    result = db.select_rows(
      [val(('texts', '*')), ('texts', '*', 'length_signal'), ('texts', '*', 'test_signal', 'flen')])
    assert list(result) == [{
      UUID_COLUMN: '1',
      f'texts.*.{VALUE_KEY}': ['hello', 'everybody'],
      'texts.*.test_signal.flen': lilac_items([5.0, 9.0]),
      'texts.*.length_signal': lilac_items([5, 9])
    }, {
      UUID_COLUMN: '2',
      f'texts.*.{VALUE_KEY}': ['a', 'bc', 'def'],
      'texts.*.test_signal.flen': lilac_items([1.0, 2.0, 3.0]),
      'texts.*.length_signal': lilac_items([1, 2, 3])
    }]

  def test_combining_columns(self, tmp_path: pathlib.Path, db_cls: Type[DatasetDB]) -> None:
    db = make_db(
      db_cls,
      tmp_path,
      items=[{
        UUID_COLUMN: '1',
        'text': 'hello',
        'extra': {
          'text': {
            'length_signal': 5,
            'test_signal': {
              'len': 5,
              'flen': 5.0
            }
          }
        }
      }, {
        UUID_COLUMN: '2',
        'text': 'everybody',
        'extra': {
          'text': {
            'length_signal': 9,
            'test_signal': {
              'len': 9,
              'flen': 9.0
            }
          }
        }
      }])

    # Sub-select text and test_signal.
    result = db.select_rows(['text', ('extra', 'text', 'test_signal')], combine_columns=True)
    assert list(result) == lilac_items([{
      UUID_COLUMN: '1',
      'text': 'hello',
      'extra': {
        'text': {
          'test_signal': {
            'len': 5,
            'flen': 5.0
          }
        }
      }
    }, {
      UUID_COLUMN: '2',
      'text': 'everybody',
      'extra': {
        'text': {
          'test_signal': {
            'len': 9,
            'flen': 9.0
          }
        }
      }
    }])

    # Sub-select text and length_signal.
    result = db.select_rows(['text', ('extra', 'text', 'length_signal')], combine_columns=True)
    assert list(result) == lilac_items([{
      UUID_COLUMN: '1',
      'text': 'hello',
      'extra': {
        'text': {
          'length_signal': 5
        }
      }
    }, {
      UUID_COLUMN: '2',
      'text': 'everybody',
      'extra': {
        'text': {
          'length_signal': 9
        }
      }
    }])

    # Sub-select length_signal only.
    result = db.select_rows([('extra', 'text', 'length_signal')], combine_columns=True)
    assert list(result) == lilac_items([{
      UUID_COLUMN: '1',
      'extra': {
        'text': {
          'length_signal': 5
        }
      }
    }, {
      UUID_COLUMN: '2',
      'extra': {
        'text': {
          'length_signal': 9
        }
      }
    }])

    # Aliases are ignored when combing columns.
    len_col = Column(('extra', 'text', 'length_signal'), alias='hello')
    result = db.select_rows([len_col], combine_columns=True)
    assert list(result) == lilac_items([{
      UUID_COLUMN: '1',
      'extra': {
        'text': {
          'length_signal': 5
        }
      }
    }, {
      UUID_COLUMN: '2',
      'extra': {
        'text': {
          'length_signal': 9
        }
      }
    }])

    # Works with UDFs and aliases are ignored.
    udf_col = SignalUDF(LengthSignal(), 'text', alias='ignored')
    result = db.select_rows(['text', udf_col], combine_columns=True)
    assert list(result) == lilac_items([{
      UUID_COLUMN: '1',
      'text': lilac_item('hello', {'length_signal': 5})
    }, {
      UUID_COLUMN: '2',
      'text': lilac_item('everybody', {'length_signal': 9})
    }])

  def test_udf(self, tmp_path: pathlib.Path, db_cls: Type[DatasetDB]) -> None:
    db = make_db(
      db_cls,
      tmp_path,
      items=[{
        UUID_COLUMN: '1',
        'text': 'hello'
      }, {
        UUID_COLUMN: '2',
        'text': 'everybody'
      }])

    signal_col = SignalUDF(TestSignal(), 'text')
    result = db.select_rows(['text', signal_col])

    assert list(result) == lilac_items([{
      UUID_COLUMN: '1',
      'text': 'hello',
      'test_signal(text)': {
        'len': 5,
        'flen': 5.0
      }
    }, {
      UUID_COLUMN: '2',
      'text': 'everybody',
      'test_signal(text)': {
        'len': 9,
        'flen': 9.0
      }
    }])

  def test_udf_with_filters(self, tmp_path: pathlib.Path, db_cls: Type[DatasetDB]) -> None:
    db = make_db(
      db_cls,
      tmp_path,
      items=[{
        UUID_COLUMN: '1',
        'text': 'hello'
      }, {
        UUID_COLUMN: '2',
        'text': 'everybody'
      }])

    signal_col = SignalUDF(TestSignal(), 'text')
    # Filter by source feature.
    filters: list[FilterTuple] = [('text', Comparison.EQUALS, 'everybody')]
    result = db.select_rows(['text', signal_col], filters=filters)
    assert list(result) == lilac_items([{
      UUID_COLUMN: '2',
      'text': 'everybody',
      'test_signal(text)': {
        'len': 9,
        'flen': 9.0
      }
    }])

    # Filter by transformed feature.
    filters = [(('test_signal(text)', 'len'), Comparison.LESS, 7)]
    result = db.select_rows(['text', signal_col], filters=filters)

    assert list(result) == lilac_items([{
      UUID_COLUMN: '1',
      'text': 'hello',
      'test_signal(text)': {
        'len': 5,
        'flen': 5.0
      }
    }])

    filters = [(('test_signal(text)', 'flen'), Comparison.GREATER, 6.0)]
    result = db.select_rows(['text', signal_col], filters=filters)

    assert list(result) == lilac_items([{
      UUID_COLUMN: '2',
      'text': 'everybody',
      'test_signal(text)': {
        'len': 9,
        'flen': 9.0
      }
    }])

  def test_udf_with_uuid_filter(self, tmp_path: pathlib.Path, db_cls: Type[DatasetDB]) -> None:

    db = make_db(
      db_cls,
      tmp_path,
      items=[{
        UUID_COLUMN: '1',
        'text': 'hello'
      }, {
        UUID_COLUMN: '2',
        'text': 'everybody'
      }])

    signal = LengthSignal()
    # Filter by a specific UUID.
    filters: list[FilterTuple] = [(UUID_COLUMN, Comparison.EQUALS, '1')]
    result = db.select_rows(['text', SignalUDF(signal, 'text')], filters=filters)
    assert list(result) == lilac_items([{
      UUID_COLUMN: '1',
      'text': 'hello',
      'length_signal(text)': 5
    }])
    assert signal._call_count == 1

    filters = [(UUID_COLUMN, Comparison.EQUALS, '2')]
    result = db.select_rows(['text', SignalUDF(signal, 'text')], filters=filters)
    assert list(result) == lilac_items([{
      UUID_COLUMN: '2',
      'text': 'everybody',
      'length_signal(text)': 9
    }])
    assert signal._call_count == 1 + 1

    # No filters.
    result = db.select_rows(['text', SignalUDF(signal, 'text')])
    assert list(result) == lilac_items([{
      UUID_COLUMN: '1',
      'text': 'hello',
      'length_signal(text)': 5
    }, {
      UUID_COLUMN: '2',
      'text': 'everybody',
      'length_signal(text)': 9
    }])
    assert signal._call_count == 2 + 2

  def test_udf_with_uuid_filter_repeated(self, tmp_path: pathlib.Path,
                                         db_cls: Type[DatasetDB]) -> None:

    db = make_db(
      db_cls,
      tmp_path,
      items=[{
        UUID_COLUMN: '1',
        'text': ['hello', 'hi']
      }, {
        UUID_COLUMN: '2',
        'text': ['everybody', 'bye', 'test']
      }])

    signal = LengthSignal()

    # Filter by a specific UUID.
    filters: list[FilterTuple] = [(UUID_COLUMN, Comparison.EQUALS, '1')]
    result = db.select_rows(['text', SignalUDF(signal, ('text', '*'))], filters=filters)
    assert list(result) == lilac_items([{
      UUID_COLUMN: '1',
      'text': ['hello', 'hi'],
      'length_signal(text)': [5, 2]
    }])
    assert signal._call_count == 2

    # Filter by a specific UUID.
    filters = [(UUID_COLUMN, Comparison.EQUALS, '2')]
    result = db.select_rows(['text', SignalUDF(signal, ('text', '*'))], filters=filters)
    assert list(result) == lilac_items([{
      UUID_COLUMN: '2',
      'text': ['everybody', 'bye', 'test'],
      'length_signal(text)': [9, 3, 4]
    }])
    assert signal._call_count == 2 + 3

  def test_udf_deeply_nested(self, tmp_path: pathlib.Path, db_cls: Type[DatasetDB]) -> None:
    db = make_db(
      db_cls,
      tmp_path,
      items=[{
        UUID_COLUMN: '1',
        'text': [['hello'], ['hi', 'bye']]
      }, {
        UUID_COLUMN: '2',
        'text': [['everybody', 'bye'], ['test']]
      }])

    signal = LengthSignal()

    result = db.select_rows([SignalUDF(signal, ('text', '*', '*'))])
    assert list(result) == lilac_items([{
      UUID_COLUMN: '1',
      'length_signal(text.*)': [[5], [2, 3]]
    }, {
      UUID_COLUMN: '2',
      'length_signal(text.*)': [[9, 3], [4]]
    }])
    assert signal._call_count == 6

  def test_udf_with_embedding(self, tmp_path: pathlib.Path, db_cls: Type[DatasetDB]) -> None:
    db = make_db(
      db_cls=db_cls,
      tmp_path=tmp_path,
      items=[{
        UUID_COLUMN: '1',
        'text': 'hello.',
      }, {
        UUID_COLUMN: '2',
        'text': 'hello2.',
      }])

    db.compute_signal(TestEmbedding(), 'text')

    signal_col = SignalUDF(TestEmbeddingSumSignal(), column=('text', TEST_EMBEDDING_NAME))
    result = db.select_rows([val('text'), signal_col])

    expected_result: list[Item] = [{
      UUID_COLUMN: '1',
      f'text.{VALUE_KEY}': 'hello.',
      'test_embedding_sum(text.test_embedding)': lilac_item(1.0)
    }, {
      UUID_COLUMN: '2',
      f'text.{VALUE_KEY}': 'hello2.',
      'test_embedding_sum(text.test_embedding)': lilac_item(2.0)
    }]
    assert list(result) == expected_result

    # Select rows with alias.
    signal_col = SignalUDF(
      TestEmbeddingSumSignal(), Column(('text', TEST_EMBEDDING_NAME)), alias='emb_sum')
    result = db.select_rows([val('text'), signal_col])
    expected_result = [{
      UUID_COLUMN: '1',
      f'text.{VALUE_KEY}': 'hello.',
      'emb_sum': lilac_item(1.0)
    }, {
      UUID_COLUMN: '2',
      f'text.{VALUE_KEY}': 'hello2.',
      'emb_sum': lilac_item(2.0)
    }]
    assert list(result) == expected_result

  def test_udf_with_nested_embedding(self, tmp_path: pathlib.Path, db_cls: Type[DatasetDB]) -> None:
    db = make_db(
      db_cls=db_cls,
      tmp_path=tmp_path,
      items=[{
        UUID_COLUMN: '1',
        'text': ['hello.', 'hello world.'],
      }, {
        UUID_COLUMN: '2',
        'text': ['hello world2.', 'hello2.'],
      }])

    db.compute_signal(TestEmbedding(), ('text', '*'))

    signal_col = SignalUDF(TestEmbeddingSumSignal(), ('text', '*', TEST_EMBEDDING_NAME))
    result = db.select_rows([val(('text', '*')), signal_col])
    expected_result = [{
      UUID_COLUMN: '1',
      f'text.*.{VALUE_KEY}': ['hello.', 'hello world.'],
      'test_embedding_sum(text.*.test_embedding)': lilac_items([1.0, 3.0])
    }, {
      UUID_COLUMN: '2',
      f'text.*.{VALUE_KEY}': ['hello world2.', 'hello2.'],
      'test_embedding_sum(text.*.test_embedding)': lilac_items([4.0, 2.0])
    }]
    assert list(result) == expected_result

  def test_source_joined_with_named_signal_column(self, tmp_path: pathlib.Path,
                                                  db_cls: Type[DatasetDB]) -> None:
    db = make_db(db_cls, tmp_path, SIMPLE_ITEMS)
    assert db.manifest() == DatasetManifest(
      namespace=TEST_NAMESPACE,
      dataset_name=TEST_DATASET_NAME,
      data_schema=schema({
        UUID_COLUMN: 'string',
        'str': 'string',
        'int': 'int32',
        'bool': 'boolean',
        'float': 'float32',
      }),
      num_items=3)

    test_signal = TestSignal()
    db.compute_signal(test_signal, 'str')

    # Check the enriched dataset manifest has 'text' enriched.
    assert db.manifest() == DatasetManifest(
      namespace=TEST_NAMESPACE,
      dataset_name=TEST_DATASET_NAME,
      data_schema=schema({
        UUID_COLUMN: 'string',
        'str': field({'test_signal': signal_field({
          'len': 'int32',
          'flen': 'float32'
        })},
                     dtype='string'),
        'int': 'int32',
        'bool': 'boolean',
        'float': 'float32',
      }),
      num_items=3)

    # Select both columns, without val() on str.
    result = db.select_rows(['str', Column(('str', 'test_signal'), alias='test_signal_on_str')])

    assert list(result) == lilac_items([{
      UUID_COLUMN: '1',
      'str': lilac_item('a', {'test_signal': {
        'len': 1,
        'flen': 1.0
      }}),
      'test_signal_on_str': {
        'len': 1,
        'flen': 1.0
      }
    }, {
      UUID_COLUMN: '2',
      'str': lilac_item('b', {'test_signal': {
        'len': 1,
        'flen': 1.0
      }}),
      'test_signal_on_str': {
        'len': 1,
        'flen': 1.0
      }
    }, {
      UUID_COLUMN: '3',
      'str': lilac_item('b', {'test_signal': {
        'len': 1,
        'flen': 1.0
      }}),
      'test_signal_on_str': {
        'len': 1,
        'flen': 1.0
      }
    }])

    # Select both columns, with val() on str.
    result = db.select_rows(
      [val('str'), Column(('str', 'test_signal'), alias='test_signal_on_str')])

    assert list(result) == [{
      UUID_COLUMN: '1',
      f'str.{VALUE_KEY}': 'a',
      'test_signal_on_str': {
        'len': lilac_item(1),
        'flen': lilac_item(1.0)
      }
    }, {
      UUID_COLUMN: '2',
      f'str.{VALUE_KEY}': 'b',
      'test_signal_on_str': {
        'len': lilac_item(1),
        'flen': lilac_item(1.0)
      }
    }, {
      UUID_COLUMN: '3',
      f'str.{VALUE_KEY}': 'b',
      'test_signal_on_str': {
        'len': lilac_item(1),
        'flen': lilac_item(1.0)
      }
    }]

  def test_invalid_column_paths(self, tmp_path: pathlib.Path, db_cls: Type[DatasetDB]) -> None:
    db = make_db(
      db_cls,
      tmp_path,
      items=[{
        UUID_COLUMN: '1',
        'text': 'hello',
        'text2': ['hello', 'world'],
      }, {
        UUID_COLUMN: '2',
        'text': 'hello world',
        'text2': ['hello2', 'world2'],
      }])
    test_signal = TestSignal()
    db.compute_signal(test_signal, 'text')
    db.compute_signal(test_signal, ('text2', '*'))

    with pytest.raises(ValueError, match='Path part "invalid" not found in the dataset'):
      db.select_rows([('text', 'test_signal', 'invalid')])

    with pytest.raises(ValueError, match='Selecting a specific index of a repeated field'):
      db.select_rows([('text2', 4, 'test_signal')])

  def test_sort(self, tmp_path: pathlib.Path, db_cls: Type[DatasetDB]) -> None:
    db = make_db(db_cls, tmp_path, SIMPLE_ITEMS)

    result = db.select_rows(
      columns=[UUID_COLUMN, 'float'], sort_by=['float'], sort_order=SortOrder.ASC)

    assert list(result) == lilac_items([{
      UUID_COLUMN: '3',
      'float': 1.0
    }, {
      UUID_COLUMN: '2',
      'float': 2.0
    }, {
      UUID_COLUMN: '1',
      'float': 3.0
    }])

    result = db.select_rows(
      columns=[UUID_COLUMN, 'float'], sort_by=['float'], sort_order=SortOrder.DESC)

    assert list(result) == lilac_items([{
      UUID_COLUMN: '1',
      'float': 3.0
    }, {
      UUID_COLUMN: '2',
      'float': 2.0
    }, {
      UUID_COLUMN: '3',
      'float': 1.0
    }])

  def test_limit(self, tmp_path: pathlib.Path, db_cls: Type[DatasetDB]) -> None:
    db = make_db(db_cls, tmp_path, SIMPLE_ITEMS)

    result = db.select_rows(
      columns=[UUID_COLUMN, 'float'], sort_by=['float'], sort_order=SortOrder.ASC, limit=2)
    assert list(result) == lilac_items([{
      UUID_COLUMN: '3',
      'float': 1.0
    }, {
      UUID_COLUMN: '2',
      'float': 2.0
    }])


class TestSignal(Signal):
  name = 'test_signal'
  enrichment_type = EnrichmentType.TEXT

  @override
  def fields(self) -> Field:
    return field({'len': 'int32', 'flen': 'float32'})

  @override
  def compute(self, data: Iterable[RichData]) -> Iterable[Optional[Item]]:
    return [{'len': len(text_content), 'flen': float(len(text_content))} for text_content in data]


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
