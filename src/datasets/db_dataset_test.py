"""Implementation-agnostic tests of the Dataset DB API."""

import os
import pathlib
from typing import Generator, Iterable, Optional, Type, cast

import numpy as np
import pytest
from typing_extensions import override

from ..embeddings.embedding_index import GetEmbeddingIndexFn
from ..embeddings.embedding_registry import clear_embedding_registry, register_embed_fn
from ..schema import UUID_COLUMN, DataType, EnrichmentType, Field, Item, ItemValue, RichData, Schema
from ..signals.signal import Signal
from ..signals.signal_registry import clear_signal_registry, register_signal
from ..signals.splitters.splitter import (
    TEXT_SPAN_END_FEATURE,
    TEXT_SPAN_FEATURE_NAME,
    TEXT_SPAN_START_FEATURE,
    SpanFields,
    SpanItem,
)
from .db_dataset import Column, DatasetDB, DatasetManifest, SortOrder
from .db_dataset_duckdb import DatasetDuckDB
from .db_dataset_test_utils import TEST_DATASET_NAME, TEST_NAMESPACE, make_db

ALL_DBS = [DatasetDuckDB]

SIMPLE_DATASET_NAME = 'simple'

SIMPLE_ITEMS: list[Item] = [{
    UUID_COLUMN: b'1' * 16,
    'str': 'a',
    'int': 1,
    'bool': False,
    'float': 3.0
}, {
    UUID_COLUMN: b'2' * 16,
    'str': 'b',
    'int': 2,
    'bool': True,
    'float': 2.0
}, {
    UUID_COLUMN: b'2' * 16,
    'str': 'b',
    'int': 2,
    'bool': True,
    'float': 1.0
}]

SIMPLE_SCHEMA = Schema(
    fields={
        UUID_COLUMN: Field(dtype=DataType.BINARY),
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


def embed(examples: Iterable[RichData]) -> np.ndarray:
  """Embed the examples, use a hashmap to the vector for simplicity."""
  return np.array([STR_EMBEDDINGS[cast(str, example)] for example in examples])


@pytest.fixture(scope='module', autouse=True)
def setup_teardown() -> Iterable[None]:
  # Setup.
  register_signal(TestSignal)
  register_signal(TestSplitterWithLen)
  register_signal(TestEmbeddingSumSignal)
  # We register the embed function like this so we can mock it and assert how many times its called.
  register_embed_fn(TEST_EMBEDDING_NAME)(embed)

  # Unit test runs.
  yield

  # Teardown.
  clear_signal_registry()
  clear_embedding_registry()


@pytest.fixture(autouse=True)
def set_data_path(tmp_path: pathlib.Path) -> Generator:
  data_path = os.environ.get('LILAC_DATA_PATH', None)
  os.environ['LILAC_DATA_PATH'] = str(tmp_path)

  yield

  os.environ['LILAC_DATA_PATH'] = data_path or ''


@pytest.mark.parametrize('db_cls', ALL_DBS)
class SelectRowsSuite:

  def test_default(self, tmp_path: pathlib.Path, db_cls: Type[DatasetDB]) -> None:
    db = make_db(db_cls, tmp_path, SIMPLE_ITEMS, SIMPLE_SCHEMA)

    result = db.select_rows()

    assert list(result) == SIMPLE_ITEMS

  def test_columns(self, tmp_path: pathlib.Path, db_cls: Type[DatasetDB]) -> None:
    db = make_db(db_cls, tmp_path, SIMPLE_ITEMS, SIMPLE_SCHEMA)

    result = db.select_rows(columns=['str', 'float'])

    assert list(result) == [{
        UUID_COLUMN: b'1' * 16,
        'str': 'a',
        'float': 3.0
    }, {
        UUID_COLUMN: b'2' * 16,
        'str': 'b',
        'float': 2.0
    }, {
        UUID_COLUMN: b'2' * 16,
        'str': 'b',
        'float': 1.0
    }]

  def test_source_joined_with_signal_column(self, tmp_path: pathlib.Path,
                                            db_cls: Type[DatasetDB]) -> None:
    db = make_db(db_cls, tmp_path, SIMPLE_ITEMS, SIMPLE_SCHEMA)
    assert db.manifest() == DatasetManifest(namespace=TEST_NAMESPACE,
                                            dataset_name=TEST_DATASET_NAME,
                                            data_schema=Schema(
                                                fields={
                                                    UUID_COLUMN: Field(dtype=DataType.BINARY),
                                                    'str': Field(dtype=DataType.STRING),
                                                    'int': Field(dtype=DataType.INT64),
                                                    'bool': Field(dtype=DataType.BOOLEAN),
                                                    'float': Field(dtype=DataType.FLOAT64),
                                                }))

    test_signal = TestSignal()
    db.compute_signal_columns(signal=test_signal, column='str')

    result = db.select_rows(columns=['str', 'test_signal(str)'])

    assert list(result) == [{
        UUID_COLUMN: b'1' * 16,
        'str': 'a',
        'test_signal(str)': {
            'len': 1,
            'flen': 1.0
        }
    }, {
        UUID_COLUMN: b'2' * 16,
        'str': 'b',
        'test_signal(str)': {
            'len': 1,
            'flen': 1.0
        }
    }, {
        UUID_COLUMN: b'2' * 16,
        'str': 'b',
        'test_signal(str)': {
            'len': 1,
            'flen': 1.0
        }
    }]

    # Check the enriched dataset manifest has 'text' enriched.
    assert db.manifest() == DatasetManifest(namespace=TEST_NAMESPACE,
                                            dataset_name=TEST_DATASET_NAME,
                                            data_schema=Schema(
                                                fields={
                                                    UUID_COLUMN:
                                                        Field(dtype=DataType.BINARY),
                                                    'str':
                                                        Field(dtype=DataType.STRING),
                                                    'int':
                                                        Field(dtype=DataType.INT64),
                                                    'bool':
                                                        Field(dtype=DataType.BOOLEAN),
                                                    'float':
                                                        Field(dtype=DataType.FLOAT64),
                                                    'test_signal(str)':
                                                        Field(fields={
                                                            'len': Field(dtype=DataType.INT32),
                                                            'flen': Field(dtype=DataType.FLOAT32)
                                                        },
                                                              enriched=True)
                                                }))

    # Select a specific signal leaf test_signal.flen.
    result = db.select_rows(columns=['str', ('test_signal(str)', 'flen')])

    assert list(result) == [{
        UUID_COLUMN: b'1' * 16,
        'str': 'a',
        'test_signal(str).flen': 1.0
    }, {
        UUID_COLUMN: b'2' * 16,
        'str': 'b',
        'test_signal(str).flen': 1.0
    }, {
        UUID_COLUMN: b'2' * 16,
        'str': 'b',
        'test_signal(str).flen': 1.0
    }]

    # Select multiple signal leafs with aliasing.
    result = db.select_rows(columns=[
        'str',
        Column(('test_signal(str)', 'flen'), alias='flen'),
        Column(('test_signal(str)', 'len'), alias='len')
    ])

    assert list(result) == [{
        UUID_COLUMN: b'1' * 16,
        'str': 'a',
        'flen': 1.0,
        'len': 1
    }, {
        UUID_COLUMN: b'2' * 16,
        'str': 'b',
        'flen': 1.0,
        'len': 1
    }, {
        UUID_COLUMN: b'2' * 16,
        'str': 'b',
        'flen': 1.0,
        'len': 1
    }]

  def test_signal_on_repeated_field(self, tmp_path: pathlib.Path, db_cls: Type[DatasetDB]) -> None:
    db = make_db(db_cls,
                 tmp_path,
                 items=[{
                     UUID_COLUMN: b'1' * 16,
                     'text': ['hello', 'everybody'],
                 }, {
                     UUID_COLUMN: b'2' * 16,
                     'text': ['hello2', 'everybody2'],
                 }],
                 schema=Schema(
                     fields={
                         UUID_COLUMN: Field(dtype=DataType.BINARY),
                         'text': Field(repeated_field=Field(dtype=DataType.STRING)),
                     }))
    test_signal = TestSignal()
    # Run the signal on the repeated field.
    db.compute_signal_columns(signal=test_signal, column=('text', '*'))

    # Check the enriched dataset manifest has 'text' enriched.
    assert db.manifest() == DatasetManifest(
        namespace=TEST_NAMESPACE,
        dataset_name=TEST_DATASET_NAME,
        data_schema=Schema(
            fields={
                UUID_COLUMN:
                    Field(dtype=DataType.BINARY),
                'text':
                    Field(repeated_field=Field(dtype=DataType.STRING)),
                'test_signal(text)':
                    Field(repeated_field=Field(fields={
                        'len': Field(dtype=DataType.INT32),
                        'flen': Field(dtype=DataType.FLOAT32)
                    },
                                               enriched=True),
                          enriched=True)
            }))

    result = db.select_rows(columns=[('test_signal(text)')])

    assert list(result) == [{
        UUID_COLUMN: b'1' * 16,
        'test_signal(text)': [{
            'len': 5,
            'flen': 5.0
        }, {
            'len': 9,
            'flen': 9.0
        }]
    }, {
        UUID_COLUMN: b'2' * 16,
        'test_signal(text)': [{
            'len': 6,
            'flen': 6.0
        }, {
            'len': 10,
            'flen': 10.0
        }]
    }]

  def test_source_joined_with_named_signal_column(self, tmp_path: pathlib.Path,
                                                  db_cls: Type[DatasetDB]) -> None:
    db = make_db(db_cls, tmp_path, SIMPLE_ITEMS, SIMPLE_SCHEMA)
    assert db.manifest() == DatasetManifest(namespace=TEST_NAMESPACE,
                                            dataset_name=TEST_DATASET_NAME,
                                            data_schema=Schema(
                                                fields={
                                                    UUID_COLUMN: Field(dtype=DataType.BINARY),
                                                    'str': Field(dtype=DataType.STRING),
                                                    'int': Field(dtype=DataType.INT64),
                                                    'bool': Field(dtype=DataType.BOOLEAN),
                                                    'float': Field(dtype=DataType.FLOAT64),
                                                }))

    test_signal = TestSignal()
    db.compute_signal_columns(signal=test_signal,
                              column='str',
                              signal_column_name='test_signal_on_str')

    result = db.select_rows(columns=['str', 'test_signal_on_str'])

    assert list(result) == [{
        UUID_COLUMN: b'1' * 16,
        'str': 'a',
        'test_signal_on_str': {
            'len': 1,
            'flen': 1.0
        }
    }, {
        UUID_COLUMN: b'2' * 16,
        'str': 'b',
        'test_signal_on_str': {
            'len': 1,
            'flen': 1.0
        }
    }, {
        UUID_COLUMN: b'2' * 16,
        'str': 'b',
        'test_signal_on_str': {
            'len': 1,
            'flen': 1.0
        }
    }]

    # Check the enriched dataset manifest has 'text' enriched.
    assert db.manifest() == DatasetManifest(namespace=TEST_NAMESPACE,
                                            dataset_name=TEST_DATASET_NAME,
                                            data_schema=Schema(
                                                fields={
                                                    UUID_COLUMN:
                                                        Field(dtype=DataType.BINARY),
                                                    'str':
                                                        Field(dtype=DataType.STRING),
                                                    'int':
                                                        Field(dtype=DataType.INT64),
                                                    'bool':
                                                        Field(dtype=DataType.BOOLEAN),
                                                    'float':
                                                        Field(dtype=DataType.FLOAT64),
                                                    'test_signal_on_str':
                                                        Field(fields={
                                                            'len': Field(dtype=DataType.INT32),
                                                            'flen': Field(dtype=DataType.FLOAT32)
                                                        },
                                                              enriched=True)
                                                }))

  def test_text_splitter(self, tmp_path: pathlib.Path, db_cls: Type[DatasetDB]) -> None:
    db = make_db(db_cls=db_cls,
                 tmp_path=tmp_path,
                 items=[{
                     UUID_COLUMN: b'1' * 16,
                     'text': '[1, 1] first sentence. [1, 1] second sentence.',
                 }, {
                     UUID_COLUMN: b'2' * 16,
                     'text': 'b2 [2, 1] first sentence. [2, 1] second sentence.',
                 }],
                 schema=Schema(fields={
                     UUID_COLUMN: Field(dtype=DataType.BINARY),
                     'text': Field(dtype=DataType.STRING),
                 }))

    db.compute_signal_columns(signal=TestSplitterWithLen(), column='text')

    result = db.select_rows(columns=['text', 'test_splitter(text)'])
    expected_result = [{
        UUID_COLUMN:
            b'1' * 16,
        'text':
            '[1, 1] first sentence. [1, 1] second sentence.',
        'test_splitter(text)': [{
            'len': 22,
            TEXT_SPAN_FEATURE_NAME: {
                TEXT_SPAN_START_FEATURE: 0,
                TEXT_SPAN_END_FEATURE: 22
            }
        }, {
            'len': 23,
            TEXT_SPAN_FEATURE_NAME: {
                TEXT_SPAN_START_FEATURE: 23,
                TEXT_SPAN_END_FEATURE: 46
            }
        }]
    }, {
        UUID_COLUMN:
            b'2' * 16,
        'text':
            'b2 [2, 1] first sentence. [2, 1] second sentence.',
        'test_splitter(text)': [{
            'len': 25,
            TEXT_SPAN_FEATURE_NAME: {
                TEXT_SPAN_START_FEATURE: 0,
                TEXT_SPAN_END_FEATURE: 25
            }
        }, {
            'len': 23,
            TEXT_SPAN_FEATURE_NAME: {
                TEXT_SPAN_START_FEATURE: 26,
                TEXT_SPAN_END_FEATURE: 49
            }
        }]
    }]
    assert list(result) == expected_result

  def test_embedding_signal(self, tmp_path: pathlib.Path, db_cls: Type[DatasetDB]) -> None:
    db = make_db(db_cls=db_cls,
                 tmp_path=tmp_path,
                 items=[{
                     UUID_COLUMN: b'1' * 16,
                     'text': 'hello.',
                 }, {
                     UUID_COLUMN: b'2' * 16,
                     'text': 'hello2.',
                 }],
                 schema=Schema(fields={
                     UUID_COLUMN: Field(dtype=DataType.BINARY),
                     'text': Field(dtype=DataType.STRING),
                 }))

    db.compute_embedding_index(embedding=TEST_EMBEDDING_NAME, column='text')

    db.compute_signal_columns(signal=TestEmbeddingSumSignal(embedding=TEST_EMBEDDING_NAME),
                              column='text',
                              signal_column_name='text_emb_sum')

    assert db.manifest() == DatasetManifest(
        namespace=TEST_NAMESPACE,
        dataset_name=TEST_DATASET_NAME,
        data_schema=Schema(
            fields={
                UUID_COLUMN: Field(dtype=DataType.BINARY),
                'text': Field(dtype=DataType.STRING),
                'text_emb_sum': Field(dtype=DataType.FLOAT32, enriched=True)
            }))

    result = db.select_rows(columns=['text', 'text_emb_sum'])
    expected_result = [{
        UUID_COLUMN: b'1' * 16,
        'text': 'hello.',
        'text_emb_sum': 1.0
    }, {
        UUID_COLUMN: b'2' * 16,
        'text': 'hello2.',
        'text_emb_sum': 2.0
    }]
    assert list(result) == expected_result

  def test_embedding_signal_splits(self, tmp_path: pathlib.Path, db_cls: Type[DatasetDB]) -> None:
    db = make_db(db_cls=db_cls,
                 tmp_path=tmp_path,
                 items=[{
                     UUID_COLUMN: b'1' * 16,
                     'text': 'hello. hello2.',
                 }, {
                     UUID_COLUMN: b'2' * 16,
                     'text': 'hello world. hello world2.',
                 }],
                 schema=Schema(fields={
                     UUID_COLUMN: Field(dtype=DataType.BINARY),
                     'text': Field(dtype=DataType.STRING),
                 }))

    db.compute_signal_columns(signal=TestSplitterWithLen(),
                              column='text',
                              signal_column_name='text_sentences')

    db.compute_embedding_index(embedding=TEST_EMBEDDING_NAME,
                               column=('text_sentences', '*', TEXT_SPAN_FEATURE_NAME))

    db.compute_signal_columns(signal=TestEmbeddingSumSignal(embedding=TEST_EMBEDDING_NAME),
                              column=('text_sentences', '*', TEXT_SPAN_FEATURE_NAME),
                              signal_column_name='text_sentences_emb_sum')

    assert db.manifest() == DatasetManifest(
        namespace=TEST_NAMESPACE,
        dataset_name=TEST_DATASET_NAME,
        data_schema=Schema(
            fields={
                UUID_COLUMN:
                    Field(dtype=DataType.BINARY),
                'text':
                    Field(dtype=DataType.STRING),
                'text_sentences_emb_sum':
                    Field(repeated_field=Field(fields={
                        TEXT_SPAN_FEATURE_NAME: Field(dtype=DataType.FLOAT32, enriched=True)
                    })),
                'text_sentences':
                    Field(repeated_field=Field(
                        fields={
                            'len':
                                Field(dtype=DataType.INT32),
                            TEXT_SPAN_FEATURE_NAME:
                                Field(
                                    fields={
                                        TEXT_SPAN_START_FEATURE: Field(dtype=DataType.INT32),
                                        TEXT_SPAN_END_FEATURE: Field(dtype=DataType.INT32)
                                    })
                        }),
                          enriched=True)
            }))

    result = db.select_rows(columns=['text', 'text_sentences', 'text_sentences_emb_sum'])
    expected_result = [{
        UUID_COLUMN: b'1' * 16,
        'text': 'hello. hello2.',
        'text_sentences': [{
            TEXT_SPAN_FEATURE_NAME: {
                TEXT_SPAN_START_FEATURE: 0,
                TEXT_SPAN_END_FEATURE: 6,
            },
            'len': 6
        }, {
            TEXT_SPAN_FEATURE_NAME: {
                TEXT_SPAN_START_FEATURE: 7,
                TEXT_SPAN_END_FEATURE: 14
            },
            'len': 7
        }],
        'text_sentences_emb_sum': [{
            TEXT_SPAN_FEATURE_NAME: 1.0
        }, {
            TEXT_SPAN_FEATURE_NAME: 2.0
        }]
    }, {
        UUID_COLUMN: b'2' * 16,
        'text': 'hello world. hello world2.',
        'text_sentences': [{
            TEXT_SPAN_FEATURE_NAME: {
                TEXT_SPAN_START_FEATURE: 0,
                TEXT_SPAN_END_FEATURE: 12
            },
            'len': 12
        }, {
            TEXT_SPAN_FEATURE_NAME: {
                TEXT_SPAN_START_FEATURE: 13,
                TEXT_SPAN_END_FEATURE: 26
            },
            'len': 13
        }],
        'text_sentences_emb_sum': [{
            TEXT_SPAN_FEATURE_NAME: 3.0
        }, {
            TEXT_SPAN_FEATURE_NAME: 4.0
        }]
    }]
    assert list(result) == expected_result

  def test_invalid_column_paths(self, tmp_path: pathlib.Path, db_cls: Type[DatasetDB]) -> None:
    db = make_db(db_cls,
                 tmp_path,
                 items=[{
                     UUID_COLUMN: b'1' * 16,
                     'text': 'hello',
                     'text2': ['hello', 'world'],
                 }, {
                     UUID_COLUMN: b'2' * 16,
                     'text': 'hello world',
                     'text2': ['hello2', 'world2'],
                 }],
                 schema=Schema(
                     fields={
                         UUID_COLUMN: Field(dtype=DataType.BINARY),
                         'text': Field(dtype=DataType.STRING),
                         'text2': Field(repeated_field=Field(dtype=DataType.STRING)),
                     }))
    test_signal = TestSignal()
    db.compute_signal_columns(signal=test_signal, column='text')
    db.compute_signal_columns(signal=test_signal, column=('text2', '*'))

    with pytest.raises(ValueError, match='Path part "invalid" not found in the dataset'):
      db.select_rows(columns=[('test_signal(text)', 'invalid')])

    with pytest.raises(ValueError, match='Selecting a specific index of a repeated field'):
      db.select_rows(columns=[('test_signal(text2)', 4)])

  def test_sort(self, tmp_path: pathlib.Path, db_cls: Type[DatasetDB]) -> None:
    db = make_db(db_cls, tmp_path, SIMPLE_ITEMS, SIMPLE_SCHEMA)

    result = db.select_rows(columns=[UUID_COLUMN, 'float'],
                            sort_by=['float'],
                            sort_order=SortOrder.ASC)

    assert list(result) == [{
        UUID_COLUMN: b'2' * 16,
        'float': 1.0
    }, {
        UUID_COLUMN: b'2' * 16,
        'float': 2.0
    }, {
        UUID_COLUMN: b'1' * 16,
        'float': 3.0
    }]

    result = db.select_rows(columns=[UUID_COLUMN, 'float'],
                            sort_by=['float'],
                            sort_order=SortOrder.DESC)

    assert list(result) == [{
        UUID_COLUMN: b'1' * 16,
        'float': 3.0
    }, {
        UUID_COLUMN: b'2' * 16,
        'float': 2.0
    }, {
        UUID_COLUMN: b'2' * 16,
        'float': 1.0
    }]

  def test_limit(self, tmp_path: pathlib.Path, db_cls: Type[DatasetDB]) -> None:
    db = make_db(db_cls, tmp_path, SIMPLE_ITEMS, SIMPLE_SCHEMA)

    result = db.select_rows(columns=[UUID_COLUMN, 'float'],
                            sort_by=['float'],
                            sort_order=SortOrder.ASC,
                            limit=2)
    assert list(result) == [{
        UUID_COLUMN: b'2' * 16,
        'float': 1.0
    }, {
        UUID_COLUMN: b'2' * 16,
        'float': 2.0
    }]


class TestSignal(Signal):
  name = 'test_signal'
  enrichment_type = EnrichmentType.TEXT
  embedding_based = False

  @override
  def fields(self) -> Field:
    return Field(fields={'len': Field(dtype=DataType.INT32), 'flen': Field(dtype=DataType.FLOAT32)})

  @override
  def compute(
      self,
      data: Optional[Iterable[RichData]] = None,
      keys: Optional[Iterable[bytes]] = None,
      get_embedding_index: Optional[GetEmbeddingIndexFn] = None) -> Iterable[Optional[Item]]:
    if data is None:
      raise ValueError('data is not defined')
    return [{'len': len(text_content), 'flen': float(len(text_content))} for text_content in data]


class TestSplitterWithLen(Signal):
  """Split documents into sentence by splitting on period. Also produces the length as a feature."""
  name = 'test_splitter'
  enrichment_type = EnrichmentType.TEXT

  @override
  def fields(self) -> Field:
    return Field(repeated_field=Field(fields=SpanFields({'len': Field(dtype=DataType.INT32)})))

  @override
  def compute(self,
              data: Optional[Iterable[RichData]] = None,
              keys: Optional[Iterable[bytes]] = None,
              get_embedding_index: Optional[GetEmbeddingIndexFn] = None) -> Iterable[ItemValue]:
    if data is None:
      raise ValueError('Sentence splitter requires text data.')

    for text in data:
      if not isinstance(text, str):
        raise ValueError(f'Expected text to be a string, got {type(text)} instead.')
      sentences = [f'{sentence.strip()}.' for sentence in text.split('.') if sentence]
      yield [
          SpanItem(span=(text.index(sentence), text.index(sentence) + len(sentence)),
                   item={'len': len(sentence)}) for sentence in sentences
      ]


class TestEmbeddingSumSignal(Signal):
  """Sums the embeddings to return a single floating point value."""
  name = 'test_embedding_sum'
  enrichment_type = EnrichmentType.TEXT
  embedding_based = True

  @override
  def fields(self) -> Field:
    return Field(dtype=DataType.FLOAT32)

  @override
  def compute(self,
              data: Optional[Iterable[RichData]] = None,
              keys: Optional[Iterable[bytes]] = None,
              get_embedding_index: Optional[GetEmbeddingIndexFn] = None) -> Iterable[ItemValue]:
    if keys is None:
      raise ValueError('Embedding sum signal requires keys.')
    if get_embedding_index is None:
      raise ValueError('get_embedding_index is None.')
    if not self.embedding:
      raise ValueError('self.embedding is None.')

    embedding_index = get_embedding_index(self.embedding, keys)
    # The signal just sums the values of the embedding.
    embedding_sums = embedding_index.embeddings.sum(axis=1)
    for embedding_sum in embedding_sums.tolist():
      yield embedding_sum


class TestInvalidSignal(Signal):
  name = 'test_invalid_signal'
  enrichment_type = EnrichmentType.TEXT

  @override
  def fields(self) -> Field:
    return Field(dtype=DataType.INT32)

  @override
  def compute(
      self,
      data: Optional[Iterable[RichData]] = None,
      keys: Optional[Iterable[bytes]] = None,
      get_embedding_index: Optional[GetEmbeddingIndexFn] = None) -> Iterable[Optional[Item]]:
    # Return an invalid output that doesn't match the input length.
    return []


@pytest.mark.parametrize('db_cls', ALL_DBS)
class ComputeSignalItemsSuite:

  def test_signal_output_validation(self, tmp_path: pathlib.Path, db_cls: Type[DatasetDB]) -> None:
    signal = TestInvalidSignal()

    db = make_db(db_cls=db_cls,
                 tmp_path=tmp_path,
                 items=[{
                     UUID_COLUMN: b'1' * 16,
                     'text': 'hello',
                 }, {
                     UUID_COLUMN: b'2' * 16,
                     'text': 'hello world',
                 }],
                 schema=Schema(fields={
                     UUID_COLUMN: Field(dtype=DataType.BINARY),
                     'text': Field(dtype=DataType.STRING),
                 }))

    with pytest.raises(
        ValueError,
        match='The enriched outputs \\(0\\) and the input data \\(2\\) do not have the same length'
    ):
      db.compute_signal_columns(signal=signal, column=('text',))
