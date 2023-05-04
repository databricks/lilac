"""Implementation-agnostic tests of the Dataset DB API."""

import pathlib
import re
from typing import Any, Generator, Iterable, Optional, Type, cast

import numpy as np
import pandas as pd
import pytest
from pytest_mock import MockerFixture
from typing_extensions import override

from ..config import CONFIG
from ..embeddings.embedding_index import EmbeddingIndexerManifest, EmbeddingIndexInfo
from ..embeddings.embedding_registry import (
    Embedding,
    clear_embedding_registry,
    register_embedding,
)
from ..embeddings.vector_store import VectorStore
from ..schema import (
    ENTITY_FEATURE_KEY,
    LILAC_COLUMN,
    UUID_COLUMN,
    DataType,
    EnrichmentType,
    Field,
    Item,
    ItemValue,
    PathTuple,
    RichData,
    Schema,
    SignalOut,
    TextEntity,
    TextEntityField,
)
from ..signals.signal import Signal
from ..signals.signal_registry import clear_signal_registry, register_signal
from . import db_dataset, db_dataset_duckdb
from .db_dataset import (
    Column,
    Comparison,
    DatasetDB,
    DatasetManifest,
    FilterTuple,
    NamedBins,
    SignalUDF,
    SortOrder,
    StatsResult,
)
from .db_dataset_duckdb import DatasetDuckDB
from .db_dataset_test_utils import TEST_DATASET_NAME, TEST_NAMESPACE, make_db

ALL_DBS = [DatasetDuckDB]

SIMPLE_DATASET_NAME = 'simple'

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

SIMPLE_SCHEMA = Schema(
    fields={
        UUID_COLUMN: Field(dtype=DataType.STRING),
        'str': Field(dtype=DataType.STRING),
        'int': Field(dtype=DataType.INT64),
        'bool': Field(dtype=DataType.BOOLEAN),
        'float': Field(dtype=DataType.FLOAT64),
    })

TEST_EMBEDDING_NAME = 'test_embedding'

EMBEDDINGS: list[tuple[str, list[float]]] = [('hello.', [1.0, 0.0, 0.0]),
                                             ('hello2.', [1.0, 1.0, 0.0]),
                                             ('hello world.', [1.0, 1.0, 1.0]),
                                             ('hello world2.', [2.0, 1.0, 1.0])]

STR_EMBEDDINGS: dict[str, list[float]] = {text: embedding for text, embedding in EMBEDDINGS}


class TestEmbedding(Embedding):
  """A test embed function."""
  name = TEST_EMBEDDING_NAME
  enrichment_type = EnrichmentType.TEXT

  @override
  def __call__(self, data: Iterable[RichData]) -> np.ndarray:
    """Embed the examples, use a hashmap to the vector for simplicity."""
    return np.array([STR_EMBEDDINGS[cast(str, example)] for example in data])


class LengthSignal(Signal):
  name = 'length_signal'
  enrichment_type = EnrichmentType.TEXT
  vector_based = False

  _call_count: int = 0

  def fields(self) -> Field:
    return Field(dtype=DataType.INT32)

  def compute(self, data: Iterable[RichData]) -> Iterable[Optional[SignalOut]]:
    for text_content in data:
      self._call_count += 1
      yield len(text_content)


class TestParamSignal(Signal):
  name = 'param_signal'
  enrichment_type = EnrichmentType.TEXT
  param: str

  def fields(self) -> Field:
    return Field(dtype=DataType.STRING)

  def compute(self, data: Iterable[RichData]) -> Iterable[Optional[SignalOut]]:
    for text_content in data:
      yield f'{str(text_content)}_{self.param}'


@pytest.fixture(scope='module', autouse=True)
def setup_teardown() -> Iterable[None]:
  # Setup.
  register_signal(TestSignal)
  register_signal(LengthSignal)
  register_signal(TestSplitterWithLen)
  register_signal(TestEmbeddingSumSignal)
  register_signal(TestEntitySignal)
  register_signal(TestParamSignal)
  register_embedding(TestEmbedding)

  # Unit test runs.
  yield

  # Teardown.
  clear_signal_registry()
  clear_embedding_registry()


@pytest.fixture(autouse=True)
def set_data_path(tmp_path: pathlib.Path) -> Generator:
  data_path = CONFIG['LILAC_DATA_PATH']
  CONFIG['LILAC_DATA_PATH'] = str(tmp_path)

  yield

  CONFIG['LILAC_DATA_PATH'] = data_path or ''


@pytest.mark.parametrize('db_cls', ALL_DBS)
class SelectRowsSuite:

  def test_default(self, tmp_path: pathlib.Path, db_cls: Type[DatasetDB]) -> None:
    db = make_db(db_cls, tmp_path, SIMPLE_ITEMS, SIMPLE_SCHEMA)

    result = db.select_rows()
    assert list(result) == SIMPLE_ITEMS

  def test_select_ids(self, tmp_path: pathlib.Path, db_cls: Type[DatasetDB]) -> None:
    db = make_db(db_cls, tmp_path, SIMPLE_ITEMS, SIMPLE_SCHEMA)

    result = db.select_rows([UUID_COLUMN])

    assert list(result) == [{UUID_COLUMN: '1'}, {UUID_COLUMN: '2'}, {UUID_COLUMN: '3'}]

  def test_select_ids_with_limit_and_offset(self, tmp_path: pathlib.Path,
                                            db_cls: Type[DatasetDB]) -> None:
    items: list[Item] = [{UUID_COLUMN: str(i)} for i in range(10, 20)]
    db = make_db(db_cls, tmp_path, items, SIMPLE_SCHEMA)

    result = db.select_rows([UUID_COLUMN], offset=1, limit=3)
    assert list(result) == [{UUID_COLUMN: '11'}, {UUID_COLUMN: '12'}, {UUID_COLUMN: '13'}]

    result = db.select_rows([UUID_COLUMN], offset=7, limit=2)
    assert list(result) == [{UUID_COLUMN: '17'}, {UUID_COLUMN: '18'}]

    result = db.select_rows([UUID_COLUMN], offset=9, limit=200)
    assert list(result) == [{UUID_COLUMN: '19'}]

    result = db.select_rows([UUID_COLUMN], offset=10, limit=200)
    assert list(result) == []

  def test_filter_by_ids(self, tmp_path: pathlib.Path, db_cls: Type[DatasetDB]) -> None:
    db = make_db(db_cls, tmp_path, SIMPLE_ITEMS, SIMPLE_SCHEMA)

    id_filter: FilterTuple = (UUID_COLUMN, Comparison.EQUALS, '1')
    result = db.select_rows(filters=[id_filter])

    assert list(result) == [{UUID_COLUMN: '1', 'str': 'a', 'int': 1, 'bool': False, 'float': 3.0}]

    id_filter = (UUID_COLUMN, Comparison.EQUALS, '2')
    result = db.select_rows(filters=[id_filter])

    assert list(result) == [{UUID_COLUMN: '2', 'str': 'b', 'int': 2, 'bool': True, 'float': 2.0}]

    id_filter = (UUID_COLUMN, Comparison.EQUALS, b'f')
    result = db.select_rows(filters=[id_filter])

    assert list(result) == []

  def test_filter_by_list_of_ids(self, tmp_path: pathlib.Path, db_cls: Type[DatasetDB]) -> None:
    db = make_db(db_cls, tmp_path, SIMPLE_ITEMS, SIMPLE_SCHEMA)

    id_filter: FilterTuple = (UUID_COLUMN, Comparison.IN, ['1', '2'])
    result = db.select_rows(filters=[id_filter])

    assert list(result) == [{
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
    }]

  def test_columns(self, tmp_path: pathlib.Path, db_cls: Type[DatasetDB]) -> None:
    db = make_db(db_cls, tmp_path, SIMPLE_ITEMS, SIMPLE_SCHEMA)

    result = db.select_rows(['str', 'float'])

    assert list(result) == [{
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
    }]

  def test_source_joined_with_signal_column(self, tmp_path: pathlib.Path,
                                            db_cls: Type[DatasetDB]) -> None:
    db = make_db(db_cls, tmp_path, SIMPLE_ITEMS, SIMPLE_SCHEMA)
    assert db.manifest() == DatasetManifest(
        namespace=TEST_NAMESPACE,
        dataset_name=TEST_DATASET_NAME,
        data_schema=Schema(
            fields={
                UUID_COLUMN: Field(dtype=DataType.STRING),
                'str': Field(dtype=DataType.STRING),
                'int': Field(dtype=DataType.INT64),
                'bool': Field(dtype=DataType.BOOLEAN),
                'float': Field(dtype=DataType.FLOAT64),
            }),
        embedding_manifest=EmbeddingIndexerManifest(indexes=[]),
        num_items=3)

    test_signal = TestSignal()
    db.compute_signal_column(test_signal, 'str')

    result = db.select_rows(['str', (LILAC_COLUMN, 'str')])
    assert list(result) == [{
        UUID_COLUMN: '1',
        'str': 'a',
        f'{LILAC_COLUMN}.str': {
            'test_signal': {
                'len': 1,
                'flen': 1.0
            }
        }
    }, {
        UUID_COLUMN: '2',
        'str': 'b',
        f'{LILAC_COLUMN}.str': {
            'test_signal': {
                'len': 1,
                'flen': 1.0
            }
        }
    }, {
        UUID_COLUMN: '3',
        'str': 'b',
        f'{LILAC_COLUMN}.str': {
            'test_signal': {
                'len': 1,
                'flen': 1.0
            }
        }
    }]

    # Check the enriched dataset manifest has 'text' enriched.
    assert db.manifest() == DatasetManifest(
        namespace=TEST_NAMESPACE,
        dataset_name=TEST_DATASET_NAME,
        data_schema=Schema(
            fields={
                UUID_COLUMN: Field(dtype=DataType.STRING),
                'str': Field(dtype=DataType.STRING),
                'int': Field(dtype=DataType.INT64),
                'bool': Field(dtype=DataType.BOOLEAN),
                'float': Field(dtype=DataType.FLOAT64),
                LILAC_COLUMN: Field(
                    fields={
                        'str': Field(
                            fields={
                                'test_signal': Field(
                                    fields={
                                        'len': Field(dtype=DataType.INT32, derived_from=('str',)),
                                        'flen': Field(
                                            dtype=DataType.FLOAT32, derived_from=('str',))
                                    },
                                    derived_from=('str',),
                                    signal_root=True)
                            })
                    })
            }),
        embedding_manifest=EmbeddingIndexerManifest(indexes=[]),
        num_items=3)

    # Select a specific signal leaf test_signal.flen.
    result = db.select_rows(['str', (LILAC_COLUMN, 'str', 'test_signal', 'flen')])

    assert list(result) == [{
        UUID_COLUMN: '1',
        'str': 'a',
        f'{LILAC_COLUMN}.str.test_signal.flen': 1.0
    }, {
        UUID_COLUMN: '2',
        'str': 'b',
        f'{LILAC_COLUMN}.str.test_signal.flen': 1.0
    }, {
        UUID_COLUMN: '3',
        'str': 'b',
        f'{LILAC_COLUMN}.str.test_signal.flen': 1.0
    }]

    # Select multiple signal leafs with aliasing.
    result = db.select_rows([
        'str',
        Column((LILAC_COLUMN, 'str', 'test_signal', 'flen'), alias='flen'),
        Column((LILAC_COLUMN, 'str', 'test_signal', 'len'), alias='len')
    ])

    assert list(result) == [{
        UUID_COLUMN: '1',
        'str': 'a',
        'flen': 1.0,
        'len': 1
    }, {
        UUID_COLUMN: '2',
        'str': 'b',
        'flen': 1.0,
        'len': 1
    }, {
        UUID_COLUMN: '3',
        'str': 'b',
        'flen': 1.0,
        'len': 1
    }]

  def test_parameterized_signal(self, tmp_path: pathlib.Path, db_cls: Type[DatasetDB]) -> None:
    db = make_db(
        db_cls,
        tmp_path,
        items=[{
            UUID_COLUMN: '1',
            'text': 'hello'
        }, {
            UUID_COLUMN: '2',
            'text': 'everybody'
        }],
        schema=Schema(fields={
            UUID_COLUMN: Field(dtype=DataType.STRING),
            'text': Field(dtype=DataType.STRING),
        }))
    test_signal_a = TestParamSignal(param='a')
    test_signal_b = TestParamSignal(param='b')
    db.compute_signal_column(test_signal_a, 'text')
    db.compute_signal_column(test_signal_b, 'text')

    assert db.manifest() == DatasetManifest(
        namespace=TEST_NAMESPACE,
        dataset_name=TEST_DATASET_NAME,
        data_schema=Schema(
            fields={
                UUID_COLUMN: Field(dtype=DataType.STRING),
                'text': Field(dtype=DataType.STRING),
                LILAC_COLUMN: Field(
                    fields={
                        'text': Field(
                            fields={
                                'param_signal(param=a)': Field(
                                    dtype=DataType.STRING, signal_root=True, derived_from=(
                                        'text',)),
                                'param_signal(param=b)': Field(
                                    dtype=DataType.STRING, signal_root=True, derived_from=(
                                        'text',)),
                            })
                    },)
            }),
        embedding_manifest=EmbeddingIndexerManifest(indexes=[]),
        num_items=2)

    result = db.select_rows(['text', LILAC_COLUMN])
    assert list(result) == [{
        UUID_COLUMN: '1',
        'text': 'hello',
        LILAC_COLUMN: {
            'text': {
                'param_signal(param=a)': 'hello_a',
                'param_signal(param=b)': 'hello_b',
            }
        }
    }, {
        UUID_COLUMN: '2',
        'text': 'everybody',
        LILAC_COLUMN: {
            'text': {
                'param_signal(param=a)': 'everybody_a',
                'param_signal(param=b)': 'everybody_b',
            }
        }
    }]

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
        }],
        schema=Schema(fields={
            UUID_COLUMN: Field(dtype=DataType.STRING),
            'text': Field(dtype=DataType.STRING),
        }))
    test_signal = TestSignal()
    db.compute_signal_column(test_signal, 'text')
    length_signal = LengthSignal()
    db.compute_signal_column(length_signal, 'text')

    result = db.select_rows(['text', LILAC_COLUMN])
    assert list(result) == [{
        UUID_COLUMN: '1',
        'text': 'hello',
        LILAC_COLUMN: {
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
        LILAC_COLUMN: {
            'text': {
                'length_signal': 9,
                'test_signal': {
                    'len': 9,
                    'flen': 9.0
                }
            }
        }
    }]

    # Test subselection.
    result = db.select_rows(['text', (LILAC_COLUMN, 'text')])
    assert list(result) == [{
        UUID_COLUMN: '1',
        'text': 'hello',
        f'{LILAC_COLUMN}.text': {
            'length_signal': 5,
            'test_signal': {
                'len': 5,
                'flen': 5.0
            }
        }
    }, {
        UUID_COLUMN: '2',
        'text': 'everybody',
        f'{LILAC_COLUMN}.text': {
            'length_signal': 9,
            'test_signal': {
                'len': 9,
                'flen': 9.0
            }
        }
    }]

    result = db.select_rows([
        'text', (LILAC_COLUMN, 'text', 'test_signal', 'flen'),
        (LILAC_COLUMN, 'text', 'test_signal', 'len')
    ])
    assert list(result) == [{
        UUID_COLUMN: '1',
        'text': 'hello',
        f'{LILAC_COLUMN}.text.test_signal.flen': 5.0,
        f'{LILAC_COLUMN}.text.test_signal.len': 5
    }, {
        UUID_COLUMN: '2',
        'text': 'everybody',
        f'{LILAC_COLUMN}.text.test_signal.flen': 9.0,
        f'{LILAC_COLUMN}.text.test_signal.len': 9
    }]

    # Test subselection with aliasing.
    result = db.select_rows(
        columns=['text',
                 Column((LILAC_COLUMN, 'text', 'test_signal', 'len'), alias='metadata')])
    assert list(result) == [{
        UUID_COLUMN: '1',
        'text': 'hello',
        'metadata': 5
    }, {
        UUID_COLUMN: '2',
        'text': 'everybody',
        'metadata': 9
    }]

    result = db.select_rows(
        columns=['text', Column((LILAC_COLUMN, 'text'), alias='text_enrichment')])
    assert list(result) == [{
        UUID_COLUMN: '1',
        'text': 'hello',
        'text_enrichment': {
            'length_signal': 5,
            'test_signal': {
                'len': 5,
                'flen': 5.0
            }
        }
    }, {
        UUID_COLUMN: '2',
        'text': 'everybody',
        'text_enrichment': {
            'length_signal': 9,
            'test_signal': {
                'len': 9,
                'flen': 9.0
            }
        }
    }]

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
        }],
        schema=Schema(
            fields={
                UUID_COLUMN: Field(dtype=DataType.STRING),
                'texts': Field(repeated_field=Field(dtype=DataType.STRING)),
            }))

    db.compute_signal_column(TestSignal(), ('texts', '*'))
    db.compute_signal_column(LengthSignal(), ('texts', '*'))

    assert db.manifest() == DatasetManifest(
        namespace=TEST_NAMESPACE,
        dataset_name=TEST_DATASET_NAME,
        data_schema=Schema(
            fields={
                UUID_COLUMN: Field(dtype=DataType.STRING),
                'texts': Field(repeated_field=Field(dtype=DataType.STRING)),
                LILAC_COLUMN: Field(
                    fields={
                        'texts': Field(
                            repeated_field=Field(
                                fields={
                                    'length_signal': Field(
                                        dtype=DataType.INT32,
                                        derived_from=('texts', '*'),
                                        signal_root=True),
                                    'test_signal': Field(
                                        fields={
                                            'len': Field(
                                                dtype=DataType.INT32, derived_from=('texts', '*')),
                                            'flen': Field(
                                                dtype=DataType.FLOAT32, derived_from=('texts', '*'))
                                        },
                                        derived_from=('texts', '*'),
                                        signal_root=True)
                                }))
                    })
            }),
        embedding_manifest=EmbeddingIndexerManifest(indexes=[]),
        num_items=2)

    result = db.select_rows(['texts', LILAC_COLUMN])
    assert list(result) == [{
        UUID_COLUMN: '1',
        'texts': ['hello', 'everybody'],
        LILAC_COLUMN: {
            'texts': [{
                'length_signal': 5,
                'test_signal': {
                    'len': 5,
                    'flen': 5.0
                }
            }, {
                'length_signal': 9,
                'test_signal': {
                    'len': 9,
                    'flen': 9.0
                }
            }]
        }
    }, {
        UUID_COLUMN: '2',
        'texts': ['a', 'bc', 'def'],
        LILAC_COLUMN: {
            'texts': [{
                'length_signal': 1,
                'test_signal': {
                    'len': 1,
                    'flen': 1.0
                }
            }, {
                'length_signal': 2,
                'test_signal': {
                    'len': 2,
                    'flen': 2.0
                }
            }, {
                'length_signal': 3,
                'test_signal': {
                    'len': 3,
                    'flen': 3.0
                }
            }]
        }
    }]

    # Test subselection.
    result = db.select_rows([
        'texts', (LILAC_COLUMN, 'texts', '*', 'length_signal'),
        (LILAC_COLUMN, 'texts', '*', 'test_signal', 'flen')
    ])
    assert list(result) == [{
        UUID_COLUMN: '1',
        'texts': ['hello', 'everybody'],
        f'{LILAC_COLUMN}.texts.*.test_signal.flen': [5.0, 9.0],
        f'{LILAC_COLUMN}.texts.*.length_signal': [5, 9]
    }, {
        UUID_COLUMN: '2',
        'texts': ['a', 'bc', 'def'],
        f'{LILAC_COLUMN}.texts.*.test_signal.flen': [1.0, 2.0, 3.0],
        f'{LILAC_COLUMN}.texts.*.length_signal': [1, 2, 3]
    }]

  def test_signal_on_repeated_field(self, tmp_path: pathlib.Path, db_cls: Type[DatasetDB]) -> None:
    db = make_db(
        db_cls,
        tmp_path,
        items=[{
            UUID_COLUMN: '1',
            'text': ['hello', 'everybody'],
        }, {
            UUID_COLUMN: '2',
            'text': ['hello2', 'everybody2'],
        }],
        schema=Schema(
            fields={
                UUID_COLUMN: Field(dtype=DataType.STRING),
                'text': Field(repeated_field=Field(dtype=DataType.STRING)),
            }))
    test_signal = TestSignal()
    # Run the signal on the repeated field.
    db.compute_signal_column(test_signal, ('text', '*'))

    # Check the enriched dataset manifest has 'text' enriched.
    assert db.manifest() == DatasetManifest(
        namespace=TEST_NAMESPACE,
        dataset_name=TEST_DATASET_NAME,
        data_schema=Schema(
            fields={
                UUID_COLUMN: Field(dtype=DataType.STRING),
                'text': Field(repeated_field=Field(dtype=DataType.STRING)),
                LILAC_COLUMN: Field(
                    fields={
                        'text': Field(
                            repeated_field=Field(
                                fields={
                                    'test_signal': Field(
                                        fields={
                                            'len': Field(
                                                dtype=DataType.INT32, derived_from=('text', '*')),
                                            'flen': Field(
                                                dtype=DataType.FLOAT32, derived_from=('text', '*'))
                                        },
                                        derived_from=('text', '*'),
                                        signal_root=True)
                                }))
                    })
            }),
        embedding_manifest=EmbeddingIndexerManifest(indexes=[]),
        num_items=2)

    result = db.select_rows([(LILAC_COLUMN, 'text', '*')])

    assert list(result) == [{
        UUID_COLUMN: '1',
        f'{LILAC_COLUMN}.text.*': [{
            'test_signal': {
                'len': 5,
                'flen': 5.0
            }
        }, {
            'test_signal': {
                'len': 9,
                'flen': 9.0
            }
        }]
    }, {
        UUID_COLUMN: '2',
        f'{LILAC_COLUMN}.text.*': [{
            'test_signal': {
                'len': 6,
                'flen': 6.0
            }
        }, {
            'test_signal': {
                'len': 10,
                'flen': 10.0
            }
        }]
    }]

  def test_signal_transform(self, tmp_path: pathlib.Path, db_cls: Type[DatasetDB]) -> None:
    db = make_db(
        db_cls,
        tmp_path,
        items=[{
            UUID_COLUMN: '1',
            'text': 'hello'
        }, {
            UUID_COLUMN: '2',
            'text': 'everybody'
        }],
        schema=Schema(fields={
            UUID_COLUMN: Field(dtype=DataType.STRING),
            'text': Field(dtype=DataType.STRING),
        }))

    signal_col = SignalUDF(TestSignal(), 'text')
    result = db.select_rows(['text', signal_col])

    assert list(result) == [{
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
    }]

  def test_signal_transform_with_filters(self, tmp_path: pathlib.Path,
                                         db_cls: Type[DatasetDB]) -> None:
    db = make_db(
        db_cls,
        tmp_path,
        items=[{
            UUID_COLUMN: '1',
            'text': 'hello'
        }, {
            UUID_COLUMN: '2',
            'text': 'everybody'
        }],
        schema=Schema(fields={
            UUID_COLUMN: Field(dtype=DataType.STRING),
            'text': Field(dtype=DataType.STRING),
        }))

    signal_col = SignalUDF(TestSignal(), 'text')
    # Filter by source feature.
    filters: list[FilterTuple] = [('text', Comparison.EQUALS, 'everybody')]
    result = db.select_rows(['text', signal_col], filters=filters)
    assert list(result) == [{
        UUID_COLUMN: '2',
        'text': 'everybody',
        'test_signal(text)': {
            'len': 9,
            'flen': 9.0
        }
    }]

    # Filter by transformed feature.
    filters = [(('test_signal(text)', 'len'), Comparison.LESS, 7)]
    result = db.select_rows(['text', signal_col], filters=filters)

    assert list(result) == [{
        UUID_COLUMN: '1',
        'text': 'hello',
        'test_signal(text)': {
            'len': 5,
            'flen': 5.0
        }
    }]

    filters = [(('test_signal(text)', 'flen'), Comparison.GREATER, 6.0)]
    result = db.select_rows(['text', signal_col], filters=filters)

    assert list(result) == [{
        UUID_COLUMN: '2',
        'text': 'everybody',
        'test_signal(text)': {
            'len': 9,
            'flen': 9.0
        }
    }]

  def test_signal_transform_with_uuid_filter(self, tmp_path: pathlib.Path,
                                             db_cls: Type[DatasetDB]) -> None:

    db = make_db(
        db_cls,
        tmp_path,
        items=[{
            UUID_COLUMN: '1',
            'text': 'hello'
        }, {
            UUID_COLUMN: '2',
            'text': 'everybody'
        }],
        schema=Schema(fields={
            UUID_COLUMN: Field(dtype=DataType.STRING),
            'text': Field(dtype=DataType.STRING),
        }))

    signal = LengthSignal()
    # Filter by a specific UUID.
    filters: list[FilterTuple] = [(UUID_COLUMN, Comparison.EQUALS, '1')]
    result = db.select_rows(['text', SignalUDF(signal, 'text')], filters=filters)
    assert list(result) == [{UUID_COLUMN: '1', 'text': 'hello', 'length_signal(text)': 5}]
    assert signal._call_count == 1

    filters = [(UUID_COLUMN, Comparison.EQUALS, '2')]
    result = db.select_rows(['text', SignalUDF(signal, 'text')], filters=filters)
    assert list(result) == [{UUID_COLUMN: '2', 'text': 'everybody', 'length_signal(text)': 9}]
    assert signal._call_count == 1 + 1

    # No filters.
    result = db.select_rows(['text', SignalUDF(signal, 'text')])
    assert list(result) == [{
        UUID_COLUMN: '1',
        'text': 'hello',
        'length_signal(text)': 5
    }, {
        UUID_COLUMN: '2',
        'text': 'everybody',
        'length_signal(text)': 9
    }]
    assert signal._call_count == 2 + 2

  def test_signal_transform_with_uuid_filter_repeated(self, tmp_path: pathlib.Path,
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
        }],
        schema=Schema(
            fields={
                UUID_COLUMN: Field(dtype=DataType.STRING),
                'text': Field(repeated_field=Field(dtype=DataType.STRING)),
            }))

    signal = LengthSignal()

    # Filter by a specific UUID.
    filters: list[FilterTuple] = [(UUID_COLUMN, Comparison.EQUALS, '1')]
    result = db.select_rows(['text', SignalUDF(signal, ('text', '*'))], filters=filters)
    assert list(result) == [{
        UUID_COLUMN: '1',
        'text': ['hello', 'hi'],
        'length_signal(text)': [5, 2]
    }]
    assert signal._call_count == 2

    # Filter by a specific UUID.
    filters = [(UUID_COLUMN, Comparison.EQUALS, '2')]
    result = db.select_rows(['text', SignalUDF(signal, ('text', '*'))], filters=filters)
    assert list(result) == [{
        UUID_COLUMN: '2',
        'text': ['everybody', 'bye', 'test'],
        'length_signal(text)': [9, 3, 4]
    }]
    assert signal._call_count == 2 + 3

  def test_signal_transform_deeply_nested(self, tmp_path: pathlib.Path,
                                          db_cls: Type[DatasetDB]) -> None:

    db = make_db(
        db_cls,
        tmp_path,
        items=[{
            UUID_COLUMN: '1',
            'text': [['hello'], ['hi', 'bye']]
        }, {
            UUID_COLUMN: '2',
            'text': [['everybody', 'bye'], ['test']]
        }],
        schema=Schema(
            fields={
                UUID_COLUMN: Field(dtype=DataType.STRING),
                'text': Field(repeated_field=Field(repeated_field=Field(dtype=DataType.STRING))),
            }))

    signal = LengthSignal()

    result = db.select_rows([SignalUDF(signal, ('text', '*', '*'))])
    assert list(result) == [{
        UUID_COLUMN: '1',
        'length_signal(text_*)': [[5], [2, 3]]
    }, {
        UUID_COLUMN: '2',
        'length_signal(text_*)': [[9, 3], [4]]
    }]
    assert signal._call_count == 6

  def test_signal_transform_with_embedding(self, tmp_path: pathlib.Path,
                                           db_cls: Type[DatasetDB]) -> None:
    db = make_db(
        db_cls=db_cls,
        tmp_path=tmp_path,
        items=[{
            UUID_COLUMN: '1',
            'text': 'hello.',
        }, {
            UUID_COLUMN: '2',
            'text': 'hello2.',
        }],
        schema=Schema(fields={
            UUID_COLUMN: Field(dtype=DataType.STRING),
            'text': Field(dtype=DataType.STRING),
        }))

    db.compute_embedding_index(TEST_EMBEDDING_NAME, 'text')

    signal_col = SignalUDF(TestEmbeddingSumSignal(embedding=TEST_EMBEDDING_NAME), column='text')
    result = db.select_rows(['text', signal_col])
    expected_result = [{
        UUID_COLUMN: '1',
        'text': 'hello.',
        'test_embedding_sum(embedding=test_embedding)(text)': 1.0
    }, {
        UUID_COLUMN: '2',
        'text': 'hello2.',
        'test_embedding_sum(embedding=test_embedding)(text)': 2.0
    }]
    assert list(result) == expected_result

    # Select rows with alias.
    signal_col = SignalUDF(
        TestEmbeddingSumSignal(embedding=TEST_EMBEDDING_NAME), Column('text'), alias='emb_sum')
    result = db.select_rows(['text', signal_col])
    expected_result = [{
        UUID_COLUMN: '1',
        'text': 'hello.',
        'emb_sum': 1.0
    }, {
        UUID_COLUMN: '2',
        'text': 'hello2.',
        'emb_sum': 2.0
    }]
    assert list(result) == expected_result

  def test_signal_transform_with_nested_embedding(self, tmp_path: pathlib.Path,
                                                  db_cls: Type[DatasetDB]) -> None:
    db = make_db(
        db_cls=db_cls,
        tmp_path=tmp_path,
        items=[{
            UUID_COLUMN: '1',
            'text': ['hello.', 'hello world.'],
        }, {
            UUID_COLUMN: '2',
            'text': ['hello world2.', 'hello2.'],
        }],
        schema=Schema(
            fields={
                UUID_COLUMN: Field(dtype=DataType.STRING),
                'text': Field(repeated_field=Field(dtype=DataType.STRING)),
            }))

    db.compute_embedding_index(TEST_EMBEDDING_NAME, ('text', '*'))

    signal_col = SignalUDF(TestEmbeddingSumSignal(embedding=TEST_EMBEDDING_NAME), ('text', '*'))
    result = db.select_rows(['text', signal_col])
    expected_result = [{
        UUID_COLUMN: '1',
        'text': ['hello.', 'hello world.'],
        'test_embedding_sum(embedding=test_embedding)(text)': [1.0, 3.0]
    }, {
        UUID_COLUMN: '2',
        'text': ['hello world2.', 'hello2.'],
        'test_embedding_sum(embedding=test_embedding)(text)': [4.0, 2.0]
    }]
    assert list(result) == expected_result

  def test_source_joined_with_named_signal_column(self, tmp_path: pathlib.Path,
                                                  db_cls: Type[DatasetDB]) -> None:
    db = make_db(db_cls, tmp_path, SIMPLE_ITEMS, SIMPLE_SCHEMA)
    assert db.manifest() == DatasetManifest(
        namespace=TEST_NAMESPACE,
        dataset_name=TEST_DATASET_NAME,
        data_schema=Schema(
            fields={
                UUID_COLUMN: Field(dtype=DataType.STRING),
                'str': Field(dtype=DataType.STRING),
                'int': Field(dtype=DataType.INT64),
                'bool': Field(dtype=DataType.BOOLEAN),
                'float': Field(dtype=DataType.FLOAT64),
            }),
        embedding_manifest=EmbeddingIndexerManifest(indexes=[]),
        num_items=3)

    test_signal = TestSignal()
    db.compute_signal_column(test_signal, 'str')
    result = db.select_rows(
        ['str', Column((LILAC_COLUMN, 'str', 'test_signal'), alias='test_signal_on_str')])

    assert list(result) == [{
        UUID_COLUMN: '1',
        'str': 'a',
        'test_signal_on_str': {
            'len': 1,
            'flen': 1.0
        }
    }, {
        UUID_COLUMN: '2',
        'str': 'b',
        'test_signal_on_str': {
            'len': 1,
            'flen': 1.0
        }
    }, {
        UUID_COLUMN: '3',
        'str': 'b',
        'test_signal_on_str': {
            'len': 1,
            'flen': 1.0
        }
    }]

    # Check the enriched dataset manifest has 'text' enriched.
    assert db.manifest() == DatasetManifest(
        namespace=TEST_NAMESPACE,
        dataset_name=TEST_DATASET_NAME,
        data_schema=Schema(
            fields={
                UUID_COLUMN: Field(dtype=DataType.STRING),
                'str': Field(dtype=DataType.STRING),
                'int': Field(dtype=DataType.INT64),
                'bool': Field(dtype=DataType.BOOLEAN),
                'float': Field(dtype=DataType.FLOAT64),
                LILAC_COLUMN: Field(
                    fields={
                        'str': Field(
                            fields={
                                'test_signal': Field(
                                    fields={
                                        'len': Field(dtype=DataType.INT32, derived_from=('str',)),
                                        'flen': Field(
                                            dtype=DataType.FLOAT32, derived_from=('str',))
                                    },
                                    derived_from=('str',),
                                    signal_root=True)
                            })
                    })
            }),
        embedding_manifest=EmbeddingIndexerManifest(indexes=[]),
        num_items=3)

  def test_text_splitter(self, tmp_path: pathlib.Path, db_cls: Type[DatasetDB]) -> None:
    db = make_db(
        db_cls=db_cls,
        tmp_path=tmp_path,
        items=[{
            UUID_COLUMN: '1',
            'text': '[1, 1] first sentence. [1, 1] second sentence.',
        }, {
            UUID_COLUMN: '2',
            'text': 'b2 [2, 1] first sentence. [2, 1] second sentence.',
        }],
        schema=Schema(fields={
            UUID_COLUMN: Field(dtype=DataType.STRING),
            'text': Field(dtype=DataType.STRING),
        }))

    db.compute_signal_column(TestSplitterWithLen(), 'text')

    result = db.select_rows(['text', (LILAC_COLUMN, 'text', 'test_splitter_len')])
    expected_result = [{
        UUID_COLUMN: '1',
        'text': '[1, 1] first sentence. [1, 1] second sentence.',
        f'{LILAC_COLUMN}.text.test_splitter_len': [
            TextEntity(0, 22, metadata={'len': 22}),
            TextEntity(23, 46, metadata={'len': 23})
        ]
    }, {
        UUID_COLUMN: '2',
        'text': 'b2 [2, 1] first sentence. [2, 1] second sentence.',
        f'{LILAC_COLUMN}.text.test_splitter_len': [
            TextEntity(0, 25, metadata={'len': 25}),
            TextEntity(26, 49, metadata={'len': 23})
        ]
    }]
    assert list(result) == expected_result

  def test_entity_signal(self, tmp_path: pathlib.Path, db_cls: Type[DatasetDB]) -> None:
    db = make_db(
        db_cls=db_cls,
        tmp_path=tmp_path,
        items=[{
            UUID_COLUMN: '1',
            'text': '[1, 1] first sentence. [1, 1] second sentence.',
        }, {
            UUID_COLUMN: '2',
            'text': 'b2 [2, 1] first sentence. [2, 1] second sentence.',
        }],
        schema=Schema(fields={
            UUID_COLUMN: Field(dtype=DataType.STRING),
            'text': Field(dtype=DataType.STRING),
        }))

    signal = TestEntitySignal()
    db.compute_signal_column(signal, 'text')

    assert db.manifest() == DatasetManifest(
        namespace=TEST_NAMESPACE,
        dataset_name=TEST_DATASET_NAME,
        data_schema=Schema(
            fields={
                UUID_COLUMN: Field(dtype=DataType.STRING),
                'text': Field(dtype=DataType.STRING),
                LILAC_COLUMN: Field(
                    fields={
                        'text': Field(
                            fields={
                                'test_entity_len': Field(
                                    repeated_field=TextEntityField(
                                        metadata={
                                            'len': Field(
                                                dtype=DataType.INT32, derived_from=('text',))
                                        },
                                        derived_from=('text',)),
                                    derived_from=('text',),
                                    signal_root=True)
                            })
                    }),
            }),
        embedding_manifest=EmbeddingIndexerManifest(indexes=[]),
        num_items=2)

    # NOTE: The way this currently works is it just generates a new signal column, in the old
    # format. This will look different once entity indexes are merged.
    result = db.select_rows(['text', (LILAC_COLUMN, 'text', 'test_entity_len')])
    expected_result = [{
        UUID_COLUMN: '1',
        'text': '[1, 1] first sentence. [1, 1] second sentence.',
        f'{LILAC_COLUMN}.text.test_entity_len': [
            TextEntity(0, 22, metadata={'len': 22}),
            TextEntity(23, 46, metadata={'len': 23})
        ]
    }, {
        UUID_COLUMN: '2',
        'text': 'b2 [2, 1] first sentence. [2, 1] second sentence.',
        f'{LILAC_COLUMN}.text.test_entity_len': [
            TextEntity(0, 25, metadata={'len': 25}),
            TextEntity(26, 49, metadata={'len': 23})
        ]
    }]
    assert list(result) == expected_result

  def test_embedding_signal(self, tmp_path: pathlib.Path, db_cls: Type[DatasetDB]) -> None:
    db = make_db(
        db_cls=db_cls,
        tmp_path=tmp_path,
        items=[{
            UUID_COLUMN: '1',
            'text': 'hello.',
        }, {
            UUID_COLUMN: '2',
            'text': 'hello2.',
        }],
        schema=Schema(fields={
            UUID_COLUMN: Field(dtype=DataType.STRING),
            'text': Field(dtype=DataType.STRING),
        }))

    embedding = TestEmbedding()
    db.compute_embedding_index(embedding, 'text')

    db.compute_signal_column(TestEmbeddingSumSignal(embedding=TestEmbedding()), 'text')

    assert db.manifest() == DatasetManifest(
        namespace=TEST_NAMESPACE,
        dataset_name=TEST_DATASET_NAME,
        data_schema=Schema(
            fields={
                UUID_COLUMN: Field(dtype=DataType.STRING),
                'text': Field(dtype=DataType.STRING),
                LILAC_COLUMN: Field(
                    fields={
                        'text': Field(
                            fields={
                                'test_embedding_sum': Field(
                                    dtype=DataType.FLOAT32,
                                    derived_from=('text',),
                                    signal_root=True)
                            })
                    })
            }),
        embedding_manifest=EmbeddingIndexerManifest(
            indexes=[EmbeddingIndexInfo(column=('text',), embedding=embedding)]),
        num_items=2)

    result = db.select_rows(['text', (LILAC_COLUMN, 'text')])
    expected_result = [{
        UUID_COLUMN: '1',
        'text': 'hello.',
        f'{LILAC_COLUMN}.text': {
            'test_embedding_sum': 1.0
        }
    }, {
        UUID_COLUMN: '2',
        'text': 'hello2.',
        f'{LILAC_COLUMN}.text': {
            'test_embedding_sum': 2.0
        }
    }]
    assert list(result) == expected_result

  def test_embedding_signal_splits(self, tmp_path: pathlib.Path, db_cls: Type[DatasetDB]) -> None:
    db = make_db(
        db_cls=db_cls,
        tmp_path=tmp_path,
        items=[{
            UUID_COLUMN: '1',
            'text': 'hello. hello2.',
        }, {
            UUID_COLUMN: '2',
            'text': 'hello world. hello world2.',
        }],
        schema=Schema(fields={
            UUID_COLUMN: Field(dtype=DataType.STRING),
            'text': Field(dtype=DataType.STRING),
        }))

    entity_signal = TestEntitySignal()
    db.compute_signal_column(entity_signal, 'text')
    embedding = TestEmbedding()
    db.compute_embedding_index(embedding,
                               (LILAC_COLUMN, 'text', 'test_entity_len', '*', ENTITY_FEATURE_KEY))
    db.compute_signal_column(
        TestEmbeddingSumSignal(embedding=embedding),
        (LILAC_COLUMN, 'text', 'test_entity_len', '*', ENTITY_FEATURE_KEY))

    assert db.manifest() == DatasetManifest(
        namespace=TEST_NAMESPACE,
        dataset_name=TEST_DATASET_NAME,
        data_schema=Schema(
            fields={
                UUID_COLUMN: Field(dtype=DataType.STRING),
                'text': Field(dtype=DataType.STRING),
                LILAC_COLUMN: Field(
                    fields={
                        'text': Field(
                            fields={
                                'test_entity_len': Field(
                                    repeated_field=TextEntityField(
                                        metadata={
                                            'len': Field(
                                                dtype=DataType.INT32, derived_from=('text',))
                                        },
                                        extra_data={
                                            'test_embedding_sum': Field(
                                                dtype=DataType.FLOAT32,
                                                derived_from=(LILAC_COLUMN, 'text',
                                                              'test_entity_len', '*',
                                                              ENTITY_FEATURE_KEY),
                                                signal_root=True)
                                        },
                                        derived_from=('text',)),
                                    derived_from=('text',),
                                    signal_root=True)
                            })
                    })
            }),
        embedding_manifest=EmbeddingIndexerManifest(indexes=[
            EmbeddingIndexInfo(
                column=(LILAC_COLUMN, 'text', 'test_entity_len', '*', ENTITY_FEATURE_KEY),
                embedding=embedding)
        ]),
        num_items=2)

    result = db.select_rows(
        ['text', Column((LILAC_COLUMN, 'text', 'test_entity_len'), alias='sentences')])
    assert list(result) == [{
        UUID_COLUMN: '1',
        'text': 'hello. hello2.',
        'sentences': [
            TextEntity(0, 6, metadata={'len': 6}, extra_data={'test_embedding_sum': 1.0}),
            TextEntity(7, 14, metadata={'len': 7}, extra_data={'test_embedding_sum': 2.0})
        ]
    }, {
        UUID_COLUMN: '2',
        'text': 'hello world. hello world2.',
        'sentences': [
            TextEntity(0, 12, metadata={'len': 12}, extra_data={'test_embedding_sum': 3.0}),
            TextEntity(13, 26, metadata={'len': 13}, extra_data={'test_embedding_sum': 4.0})
        ]
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
        }],
        schema=Schema(
            fields={
                UUID_COLUMN: Field(dtype=DataType.STRING),
                'text': Field(dtype=DataType.STRING),
                'text2': Field(repeated_field=Field(dtype=DataType.STRING)),
            }))
    test_signal = TestSignal()
    db.compute_signal_column(test_signal, 'text')
    db.compute_signal_column(test_signal, ('text2', '*'))

    with pytest.raises(ValueError, match='Path part "invalid" not found in the dataset'):
      db.select_rows([(LILAC_COLUMN, 'text', 'test_signal', 'invalid')])

    with pytest.raises(ValueError, match='Selecting a specific index of a repeated field'):
      db.select_rows([(LILAC_COLUMN, 'text2', 4, 'test_signal')])

  def test_sort(self, tmp_path: pathlib.Path, db_cls: Type[DatasetDB]) -> None:
    db = make_db(db_cls, tmp_path, SIMPLE_ITEMS, SIMPLE_SCHEMA)

    result = db.select_rows(
        columns=[UUID_COLUMN, 'float'], sort_by=['float'], sort_order=SortOrder.ASC)

    assert list(result) == [{
        UUID_COLUMN: '3',
        'float': 1.0
    }, {
        UUID_COLUMN: '2',
        'float': 2.0
    }, {
        UUID_COLUMN: '1',
        'float': 3.0
    }]

    result = db.select_rows(
        columns=[UUID_COLUMN, 'float'], sort_by=['float'], sort_order=SortOrder.DESC)

    assert list(result) == [{
        UUID_COLUMN: '1',
        'float': 3.0
    }, {
        UUID_COLUMN: '2',
        'float': 2.0
    }, {
        UUID_COLUMN: '3',
        'float': 1.0
    }]

  def test_limit(self, tmp_path: pathlib.Path, db_cls: Type[DatasetDB]) -> None:
    db = make_db(db_cls, tmp_path, SIMPLE_ITEMS, SIMPLE_SCHEMA)

    result = db.select_rows(
        columns=[UUID_COLUMN, 'float'], sort_by=['float'], sort_order=SortOrder.ASC, limit=2)
    assert list(result) == [{UUID_COLUMN: '3', 'float': 1.0}, {UUID_COLUMN: '2', 'float': 2.0}]


class TestSignal(Signal):
  name = 'test_signal'
  enrichment_type = EnrichmentType.TEXT
  vector_based = False

  @override
  def fields(self) -> Field:
    return Field(fields={'len': Field(dtype=DataType.INT32), 'flen': Field(dtype=DataType.FLOAT32)})

  @override
  def compute(self, data: Iterable[RichData]) -> Iterable[Optional[Item]]:
    return [{'len': len(text_content), 'flen': float(len(text_content))} for text_content in data]


class TestSplitterWithLen(Signal):
  """Split documents into sentence by splitting on period. Also produces the length as a feature."""
  name = 'test_splitter_len'
  enrichment_type = EnrichmentType.TEXT

  @override
  def fields(self) -> Field:
    return Field(repeated_field=TextEntityField(metadata={'len': Field(dtype=DataType.INT32)}))

  @override
  def compute(self, data: Iterable[RichData]) -> Iterable[ItemValue]:
    for text in data:
      if not isinstance(text, str):
        raise ValueError(f'Expected text to be a string, got {type(text)} instead.')
      sentences = [f'{sentence.strip()}.' for sentence in text.split('.') if sentence]
      yield [
          TextEntity(
              start=text.index(sentence),
              end=text.index(sentence) + len(sentence),
              metadata={'len': len(sentence)}) for sentence in sentences
      ]


class TestEntitySignal(Signal):
  """Split documents into sentence by splitting on period, generating entities.

  Also produces the length as a feature.
  """
  name = 'test_entity_len'
  enrichment_type = EnrichmentType.TEXT

  @override
  def fields(self) -> Field:
    return Field(repeated_field=TextEntityField(metadata={'len': Field(dtype=DataType.INT32)}))

  @override
  def compute(self, data: Iterable[RichData]) -> Iterable[ItemValue]:
    for text in data:
      if not isinstance(text, str):
        raise ValueError(f'Expected text to be a string, got {type(text)} instead.')
      sentences = [f'{sentence.strip()}.' for sentence in text.split('.') if sentence]
      yield [
          TextEntity(
              start=text.index(sentence),
              end=text.index(sentence) + len(sentence),
              metadata={'len': len(sentence)}) for sentence in sentences
      ]


class TestEmbeddingSumSignal(Signal):
  """Sums the embeddings to return a single floating point value."""
  name = 'test_embedding_sum'
  enrichment_type = EnrichmentType.TEXT
  vector_based = True

  @override
  def fields(self) -> Field:
    return Field(dtype=DataType.FLOAT32)

  @override
  def vector_compute(self, keys: Iterable[PathTuple],
                     vector_store: VectorStore) -> Iterable[ItemValue]:
    if not self.embedding:
      raise ValueError('self.embedding is None.')

    # The signal just sums the values of the embedding.
    embedding_sums = vector_store.get(keys).sum(axis=1)
    for embedding_sum in embedding_sums.tolist():
      yield embedding_sum


class TestInvalidSignal(Signal):
  name = 'test_invalid_signal'
  enrichment_type = EnrichmentType.TEXT

  @override
  def fields(self) -> Field:
    return Field(dtype=DataType.INT32)

  @override
  def compute(self, data: Iterable[RichData]) -> Iterable[Optional[Item]]:
    # Return an invalid output that doesn't match the input length.
    return []


@pytest.mark.parametrize('db_cls', ALL_DBS)
class ComputeSignalItemsSuite:

  def test_signal_output_validation(self, tmp_path: pathlib.Path, db_cls: Type[DatasetDB]) -> None:
    signal = TestInvalidSignal()

    db = make_db(
        db_cls=db_cls,
        tmp_path=tmp_path,
        items=[{
            UUID_COLUMN: '1',
            'text': 'hello',
        }, {
            UUID_COLUMN: '2',
            'text': 'hello world',
        }],
        schema=Schema(fields={
            UUID_COLUMN: Field(dtype=DataType.STRING),
            'text': Field(dtype=DataType.STRING),
        }))

    with pytest.raises(
        ValueError, match='The signal generated 0 values but the input data had 2 values.'):
      db.compute_signal_column(signal, 'text')


@pytest.mark.parametrize('db_cls', ALL_DBS)
class StatsSuite:

  def test_simple_stats(self, tmp_path: pathlib.Path, db_cls: Type[DatasetDB]) -> None:
    db = make_db(db_cls, tmp_path, SIMPLE_ITEMS, SIMPLE_SCHEMA)

    result = db.stats(leaf_path='str')
    assert result == StatsResult(total_count=3, approx_count_distinct=2, avg_text_length=1)

    result = db.stats(leaf_path='float')
    assert result == StatsResult(total_count=3, approx_count_distinct=3, min_val=1.0, max_val=3.0)

    result = db.stats(leaf_path='bool')
    assert result == StatsResult(total_count=3, approx_count_distinct=2)

    result = db.stats(leaf_path='int')
    assert result == StatsResult(total_count=3, approx_count_distinct=2, min_val=1, max_val=2)

  def test_nested_stats(self, tmp_path: pathlib.Path, db_cls: Type[DatasetDB]) -> None:
    nested_items: list[Item] = [
        {
            'name': 'Name1',
            'addresses': [{
                'zips': [5, 8]
            }]
        },
        {
            'name': 'Name2',
            'addresses': [{
                'zips': [3]
            }, {
                'zips': [11, 8]
            }]
        },
        {
            'name': 'Name2',
            'addresses': []
        },  # No addresses.
        {
            'name': 'Name2',
            'addresses': [{
                'zips': []
            }]
        }  # No zips in the first address.
    ]
    nested_schema = Schema(
        fields={
            UUID_COLUMN: Field(dtype=DataType.STRING),
            'name': Field(dtype=DataType.STRING),
            'addresses': Field(
                repeated_field=Field(
                    fields={'zips': Field(repeated_field=Field(dtype=DataType.INT32))}))
        })
    db = make_db(db_cls=db_cls, tmp_path=tmp_path, items=nested_items, schema=nested_schema)

    result = db.stats(leaf_path='name')
    assert result == StatsResult(total_count=4, approx_count_distinct=2, avg_text_length=5)

    result = db.stats(leaf_path='addresses.*.zips.*')
    assert result == StatsResult(total_count=5, approx_count_distinct=4, min_val=3, max_val=11)

  def test_stats_approximation(self, tmp_path: pathlib.Path, db_cls: Type[DatasetDB],
                               mocker: MockerFixture) -> None:
    sample_size = 5
    mocker.patch(f'{db_dataset_duckdb.__name__}.SAMPLE_SIZE_DISTINCT_COUNT', sample_size)

    nested_items: list[Item] = [{'feature': str(i)} for i in range(sample_size * 10)]
    nested_schema = Schema(fields={
        UUID_COLUMN: Field(dtype=DataType.STRING),
        'feature': Field(dtype=DataType.STRING)
    })
    db = make_db(db_cls=db_cls, tmp_path=tmp_path, items=nested_items, schema=nested_schema)

    result = db.stats(leaf_path='feature')
    assert result == StatsResult(total_count=50, approx_count_distinct=50, avg_text_length=1)

  def test_error_handling(self, tmp_path: pathlib.Path, db_cls: Type[DatasetDB]) -> None:
    db = make_db(db_cls=db_cls, tmp_path=tmp_path, items=SIMPLE_ITEMS, schema=SIMPLE_SCHEMA)

    with pytest.raises(ValueError, match='leaf_path must be provided'):
      db.stats(cast(Any, None))

    with pytest.raises(ValueError, match='Leaf "\\(\'unknown\',\\)" not found in dataset'):
      db.stats(leaf_path='unknown')


@pytest.mark.parametrize('db_cls', ALL_DBS)
class SelectGroupsSuite:

  def test_flat_data(self, tmp_path: pathlib.Path, db_cls: Type[DatasetDB]) -> None:
    items: list[Item] = [
        {
            'name': 'Name1',
            'age': 34,
            'active': False
        },
        {
            'name': 'Name2',
            'age': 45,
            'active': True
        },
        {
            'age': 17,
            'active': True
        },  # Missing "name".
        {
            'name': 'Name3',
            'active': True
        },  # Missing "age".
        {
            'name': 'Name4',
            'age': 55
        }  # Missing "active".
    ]
    schema = Schema(
        fields={
            UUID_COLUMN: Field(dtype=DataType.STRING),
            'name': Field(dtype=DataType.STRING),
            'age': Field(dtype=DataType.INT32),
            'active': Field(dtype=DataType.BOOLEAN)
        })
    db = make_db(db_cls=db_cls, tmp_path=tmp_path, items=items, schema=schema)

    result = db.select_groups(leaf_path='name').df()
    expected = pd.DataFrame.from_records([{
        'value': 'Name1',
        'count': 1
    }, {
        'value': 'Name2',
        'count': 1
    }, {
        'value': None,
        'count': 1
    }, {
        'value': 'Name3',
        'count': 1
    }, {
        'value': 'Name4',
        'count': 1
    }])
    pd.testing.assert_frame_equal(result, expected)

    result = db.select_groups(leaf_path='age', bins=[20, 50, 60]).df()
    expected = pd.DataFrame.from_records([
        {
            'value': 1,  # age 20-50.
            'count': 2
        },
        {
            'value': 0,  # age < 20.
            'count': 1
        },
        {
            'value': None,  # Missing age.
            'count': 1
        },
        {
            'value': 2,  # age 50-60.
            'count': 1
        }
    ])
    pd.testing.assert_frame_equal(result, expected)

    result = db.select_groups(leaf_path='active').df()
    expected = pd.DataFrame.from_records([
        {
            'value': True,
            'count': 3
        },
        {
            'value': False,
            'count': 1
        },
        {
            'value': None,  # Missing "active".
            'count': 1
        }
    ])
    pd.testing.assert_frame_equal(result, expected)

  def test_result_is_iterable(self, tmp_path: pathlib.Path, db_cls: Type[DatasetDB]) -> None:
    items: list[Item] = [
        {
            'active': False
        },
        {
            'active': True
        },
        {
            'active': True
        },
        {
            'active': True
        },
        {}  # Missing "active".
    ]
    schema = Schema(fields={
        UUID_COLUMN: Field(dtype=DataType.STRING),
        'active': Field(dtype=DataType.BOOLEAN)
    })
    db = make_db(db_cls=db_cls, tmp_path=tmp_path, items=items, schema=schema)

    result = db.select_groups(leaf_path='active')
    groups = list(result)
    assert groups == [(True, 3), (False, 1), (None, 1)]

  def test_list_of_structs(self, tmp_path: pathlib.Path, db_cls: Type[DatasetDB]) -> None:
    items: list[Item] = [{
        'list_of_structs': [{
            'name': 'a'
        }, {
            'name': 'b'
        }]
    }, {
        'list_of_structs': [{
            'name': 'c'
        }, {
            'name': 'a'
        }, {
            'name': 'd'
        }]
    }, {
        'list_of_structs': [{
            'name': 'd'
        }]
    }]
    schema = Schema(
        fields={
            UUID_COLUMN: Field(dtype=DataType.STRING),
            'list_of_structs': Field(
                repeated_field=Field(fields={'name': Field(dtype=DataType.STRING)})),
        })
    db = make_db(db_cls=db_cls, tmp_path=tmp_path, items=items, schema=schema)

    result = db.select_groups(leaf_path='list_of_structs.*.name').df()
    expected = pd.DataFrame.from_records([{
        'value': 'a',
        'count': 2
    }, {
        'value': 'd',
        'count': 2
    }, {
        'value': 'b',
        'count': 1
    }, {
        'value': 'c',
        'count': 1
    }])
    pd.testing.assert_frame_equal(result, expected)

  def test_nested_lists(self, tmp_path: pathlib.Path, db_cls: Type[DatasetDB]) -> None:
    items: list[Item] = [{
        'nested_list': [[{
            'name': 'a'
        }], [{
            'name': 'b'
        }]]
    }, {
        'nested_list': [[{
            'name': 'c'
        }, {
            'name': 'a'
        }], [{
            'name': 'd'
        }]]
    }, {
        'nested_list': [[{
            'name': 'd'
        }]]
    }]
    schema = Schema(
        fields={
            UUID_COLUMN: Field(dtype=DataType.STRING),
            'nested_list': Field(
                repeated_field=Field(
                    repeated_field=Field(fields={'name': Field(dtype=DataType.STRING)}))),
        })
    db = make_db(db_cls=db_cls, tmp_path=tmp_path, items=items, schema=schema)

    result = db.select_groups(leaf_path='nested_list.*.*.name').df()
    expected = pd.DataFrame.from_records([{
        'value': 'a',
        'count': 2
    }, {
        'value': 'd',
        'count': 2
    }, {
        'value': 'b',
        'count': 1
    }, {
        'value': 'c',
        'count': 1
    }])
    pd.testing.assert_frame_equal(result, expected)

  def test_nested_struct(self, tmp_path: pathlib.Path, db_cls: Type[DatasetDB]) -> None:
    items: list[Item] = [
        {
            'nested_struct': {
                'struct': {
                    'name': 'c'
                }
            }
        },
        {
            'nested_struct': {
                'struct': {
                    'name': 'b'
                }
            }
        },
        {
            'nested_struct': {
                'struct': {
                    'name': 'a'
                }
            }
        },
    ]
    schema = Schema(
        fields={
            UUID_COLUMN: Field(dtype=DataType.STRING),
            'nested_struct': Field(
                fields={'struct': Field(fields={'name': Field(dtype=DataType.STRING)})}),
        })
    db = make_db(db_cls=db_cls, tmp_path=tmp_path, items=items, schema=schema)

    result = db.select_groups(leaf_path='nested_struct.struct.name').df()
    expected = pd.DataFrame.from_records([{
        'value': 'c',
        'count': 1
    }, {
        'value': 'b',
        'count': 1
    }, {
        'value': 'a',
        'count': 1
    }])
    pd.testing.assert_frame_equal(result, expected)

  def test_named_bins(self, tmp_path: pathlib.Path, db_cls: Type[DatasetDB]) -> None:
    items: list[Item] = [{
        'age': 34,
    }, {
        'age': 45,
    }, {
        'age': 17,
    }, {
        'age': 80
    }, {
        'age': 55
    }]
    schema = Schema(fields={
        UUID_COLUMN: Field(dtype=DataType.STRING),
        'age': Field(dtype=DataType.INT32),
    })
    db = make_db(db_cls=db_cls, tmp_path=tmp_path, items=items, schema=schema)

    result = db.select_groups(
        leaf_path='age',
        bins=NamedBins(bins=[20, 50, 65], labels=['young', 'adult', 'middle-aged', 'senior'])).df()
    expected = pd.DataFrame.from_records([
        {
            'value': 'adult',  # age 20-50.
            'count': 2
        },
        {
            'value': 'young',  # age < 20.
            'count': 1
        },
        {
            'value': 'senior',  # age > 65.
            'count': 1
        },
        {
            'value': 'middle-aged',  # age 50-65.
            'count': 1
        }
    ])
    pd.testing.assert_frame_equal(result, expected)

  def test_invalid_leaf(self, tmp_path: pathlib.Path, db_cls: Type[DatasetDB]) -> None:
    items: list[Item] = [
        {
            'nested_struct': {
                'struct': {
                    'name': 'c'
                }
            }
        },
        {
            'nested_struct': {
                'struct': {
                    'name': 'b'
                }
            }
        },
        {
            'nested_struct': {
                'struct': {
                    'name': 'a'
                }
            }
        },
    ]
    schema = Schema(
        fields={
            UUID_COLUMN: Field(dtype=DataType.STRING),
            'nested_struct': Field(
                fields={'struct': Field(fields={'name': Field(dtype=DataType.STRING)})}),
        })
    db = make_db(db_cls=db_cls, tmp_path=tmp_path, items=items, schema=schema)

    with pytest.raises(
        ValueError, match=re.escape("Leaf \"('nested_struct',)\" not found in dataset")):
      db.select_groups(leaf_path='nested_struct')

    with pytest.raises(
        ValueError, match=re.escape("Leaf \"('nested_struct', 'struct')\" not found in dataset")):
      db.select_groups(leaf_path='nested_struct.struct')

    with pytest.raises(
        ValueError,
        match=re.escape("Leaf \"('nested_struct', 'struct', 'wrong_name')\" not found in dataset")):
      db.select_groups(leaf_path='nested_struct.struct.wrong_name')

  def test_too_many_distinct(self, tmp_path: pathlib.Path, db_cls: Type[DatasetDB],
                             mocker: MockerFixture) -> None:
    too_many_distinct = 5
    mocker.patch(f'{db_dataset.__name__}.TOO_MANY_DISTINCT', too_many_distinct)

    items: list[Item] = [{'feature': str(i)} for i in range(too_many_distinct + 10)]
    schema = Schema(fields={
        UUID_COLUMN: Field(dtype=DataType.STRING),
        'feature': Field(dtype=DataType.STRING)
    })
    db = make_db(db_cls=db_cls, tmp_path=tmp_path, items=items, schema=schema)

    with pytest.raises(
        ValueError, match=re.escape('Leaf "(\'feature\',)" has too many unique values: 15')):
      db.select_groups('feature')

  def test_bins_are_required_for_float(self, tmp_path: pathlib.Path,
                                       db_cls: Type[DatasetDB]) -> None:
    items: list[Item] = [{'feature': float(i)} for i in range(5)]
    schema = Schema(fields={
        UUID_COLUMN: Field(dtype=DataType.STRING),
        'feature': Field(dtype=DataType.FLOAT32)
    })
    db = make_db(db_cls=db_cls, tmp_path=tmp_path, items=items, schema=schema)

    with pytest.raises(
        ValueError,
        match=re.escape('"bins" needs to be defined for the int/float leaf "(\'feature\',)"')):
      db.select_groups('feature')
