"""Tests for db.compute_signal()."""

import pathlib
from typing import Generator, Iterable, Optional, Type, cast

import numpy as np
import pytest
from typing_extensions import override

from .dataset_utils import lilac_item, lilac_items, lilac_span, signal_item

from ..config import CONFIG
from ..embeddings.embedding import EmbeddingSignal
from ..embeddings.vector_store import VectorStore
from ..schema import (
  SIGNAL_METADATA_KEY,
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
from .db_dataset import Column, DatasetDB, DatasetManifest
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


class TestInvalidSignal(Signal):
  name = 'test_invalid_signal'
  enrichment_type = EnrichmentType.TEXT

  @override
  def fields(self) -> Field:
    return field('int32')

  @override
  def compute(self, data: Iterable[RichData]) -> Iterable[Optional[Item]]:
    # Return an invalid output that doesn't match the input length.
    return []


class TestSparseSignal(Signal):
  name = 'test_sparse_signal'
  enrichment_type = EnrichmentType.TEXT

  @override
  def fields(self) -> Field:
    return field('int32')

  @override
  def compute(self, data: Iterable[RichData]) -> Iterable[Optional[ItemValue]]:
    for text in data:
      if text == 'hello':
        # Skip this input.
        yield None
      else:
        yield len(text)


class TestSparseRichSignal(Signal):
  """Find personally identifiable information (emails, phone numbers, etc)."""
  name = 'test_sparse_rich_signal'
  enrichment_type = EnrichmentType.TEXT

  @override
  def fields(self) -> Field:
    return field({'emails': ['string']})

  @override
  def compute(self, data: Iterable[RichData]) -> Iterable[Optional[Item]]:
    for text in data:
      if text == 'hello':
        # Skip this input.
        yield None
      else:
        yield {'emails': ['test1@hello.com', 'test2@hello.com']}


class TestParamSignal(Signal):
  name = 'param_signal'
  enrichment_type = EnrichmentType.TEXT
  param: str

  def fields(self) -> Field:
    return field('string')

  def compute(self, data: Iterable[RichData]) -> Iterable[Optional[SignalOut]]:
    for text_content in data:
      yield f'{str(text_content)}_{self.param}'


class TestSignal(Signal):
  name = 'test_signal'
  enrichment_type = EnrichmentType.TEXT

  @override
  def fields(self) -> Field:
    return field({'len': 'int32', 'flen': 'float32'})

  @override
  def compute(self, data: Iterable[RichData]) -> Iterable[Optional[Item]]:
    return [{'len': len(text_content), 'flen': float(len(text_content))} for text_content in data]


EMBEDDINGS: list[tuple[str, list[float]]] = [('hello.', [1.0, 0.0, 0.0]),
                                             ('hello2.', [1.0, 1.0, 0.0]),
                                             ('hello world.', [1.0, 1.0, 1.0]),
                                             ('hello world2.', [2.0, 1.0, 1.0])]

STR_EMBEDDINGS: dict[str, list[float]] = {text: embedding for text, embedding in EMBEDDINGS}


class TestEmbedding(EmbeddingSignal):
  """A test embed function."""
  name = 'test_embedding'
  enrichment_type = EnrichmentType.TEXT

  @override
  def fields(self) -> Field:
    """Return the fields for the embedding."""
    # Override in the test so we can attach extra metadata.
    return Field(
      dtype=DataType.EMBEDDING,
      fields={SIGNAL_METADATA_KEY: Field(fields={'neg_sum': Field(dtype=DataType.FLOAT32)})})

  @override
  def compute(self, data: Iterable[RichData]) -> Iterable[Item]:
    """Call the embedding function."""
    embeddings = [np.array(STR_EMBEDDINGS[cast(str, example)]) for example in data]
    yield from (signal_item(e, {'neg_sum': -1 * e.sum()}) for e in embeddings)


class TestSplitSignal(Signal):
  """Split documents into sentence by splitting on period, generating entities.

  Also produces the length as a feature.
  """
  name = 'test_split_len'
  enrichment_type = EnrichmentType.TEXT

  @override
  def fields(self) -> Field:
    return field([
      Field(
        dtype=DataType.STRING_SPAN, fields={SIGNAL_METADATA_KEY: field({'len': field('int32')})})
    ])

  @override
  def compute(self, data: Iterable[RichData]) -> Iterable[ItemValue]:
    for text in data:
      if not isinstance(text, str):
        raise ValueError(f'Expected text to be a string, got {type(text)} instead.')
      sentences = [f'{sentence.strip()}.' for sentence in text.split('.') if sentence]
      yield [
        signal_item(
          lilac_span(text.index(sentence),
                     text.index(sentence) + len(sentence)), {'len': len(sentence)})
        for sentence in sentences
      ]


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


class TestSplitterWithLen(Signal):
  """Split documents into sentence by splitting on period. Also produces the length as a feature."""
  name = 'test_splitter_len'
  enrichment_type = EnrichmentType.TEXT

  @override
  def fields(self) -> Field:
    return field([
      Field(
        dtype=DataType.STRING_SPAN, fields={SIGNAL_METADATA_KEY: field({'len': field('int32')})})
    ])

  @override
  def compute(self, data: Iterable[RichData]) -> Iterable[ItemValue]:
    for text in data:
      if not isinstance(text, str):
        raise ValueError(f'Expected text to be a string, got {type(text)} instead.')
      sentences = [f'{sentence.strip()}.' for sentence in text.split('.') if sentence]
      yield [
        signal_item(
          lilac_span(text.index(sentence),
                     text.index(sentence) + len(sentence)), {'len': len(sentence)})
        for sentence in sentences
      ]


@pytest.fixture(autouse=True)
def set_data_path(tmp_path: pathlib.Path) -> Generator:
  data_path = CONFIG['LILAC_DATA_PATH']
  CONFIG['LILAC_DATA_PATH'] = str(tmp_path)
  yield
  CONFIG['LILAC_DATA_PATH'] = data_path or ''


@pytest.fixture(scope='module', autouse=True)
def setup_teardown() -> Iterable[None]:
  # Setup.
  register_signal(TestSparseSignal)
  register_signal(TestSparseRichSignal)
  register_signal(TestParamSignal)
  register_signal(TestSignal)
  register_signal(TestEmbedding)
  register_signal(TestSplitSignal)
  register_signal(TestEmbeddingSumSignal)
  register_signal(TestSplitterWithLen)
  # Unit test runs.
  yield
  # Teardown.
  clear_signal_registry()


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
      }])

    with pytest.raises(
        ValueError, match='The signal generated 0 values but the input data had 2 values.'):
      db.compute_signal(signal, 'text')

  def test_sparse_signal(self, tmp_path: pathlib.Path, db_cls: Type[DatasetDB]) -> None:
    db = make_db(
      db_cls=db_cls,
      tmp_path=tmp_path,
      items=[{
        UUID_COLUMN: '1',
        'text': 'hello',
      }, {
        UUID_COLUMN: '2',
        'text': 'hello world',
      }])

    db.compute_signal(TestSparseSignal(), 'text')

    result = db.select_rows(['text', LILAC_COLUMN])
    assert list(result) == lilac_items([{
      UUID_COLUMN: '1',
      'text': 'hello',
      LILAC_COLUMN: {
        'text': {
          'test_sparse_signal': None
        }
      }
    }, {
      UUID_COLUMN: '2',
      'text': 'hello world',
      LILAC_COLUMN: {
        'text': {
          'test_sparse_signal': 11
        }
      }
    }])

  def test_sparse_rich_signal(self, tmp_path: pathlib.Path, db_cls: Type[DatasetDB]) -> None:
    db = make_db(
      db_cls=db_cls,
      tmp_path=tmp_path,
      items=[{
        UUID_COLUMN: '1',
        'text': 'hello',
      }, {
        UUID_COLUMN: '2',
        'text': 'hello world',
      }])

    db.compute_signal(TestSparseRichSignal(), 'text')

    result = db.select_rows(['text', LILAC_COLUMN])
    assert list(result) == lilac_items([{
      UUID_COLUMN: '1',
      'text': 'hello',
      LILAC_COLUMN: {
        'text': {
          'test_sparse_rich_signal': None
        }
      }
    }, {
      UUID_COLUMN: '2',
      'text': 'hello world',
      LILAC_COLUMN: {
        'text': {
          'test_sparse_rich_signal': {
            'emails': ['test1@hello.com', 'test2@hello.com']
          }
        }
      }
    }])

  def test_source_joined_with_signal_column(self, tmp_path: pathlib.Path,
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

    result = db.select_rows(['str', (LILAC_COLUMN, 'str')])
    assert list(result) == lilac_items([{
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
    }])

    # Check the enriched dataset manifest has 'text' enriched.
    assert db.manifest() == DatasetManifest(
      namespace=TEST_NAMESPACE,
      dataset_name=TEST_DATASET_NAME,
      data_schema=schema({
        UUID_COLUMN: 'string',
        'str': 'string',
        'int': 'int32',
        'bool': 'boolean',
        'float': 'float32',
        LILAC_COLUMN: {
          'str': {
            'test_signal': signal_field({
              'len': 'int32',
              'flen': 'float32'
            }),
          }
        }
      }),
      num_items=3)

    # Select a specific signal leaf test_signal.flen.
    result = db.select_rows(['str', (LILAC_COLUMN, 'str', 'test_signal', 'flen')])

    assert list(result) == lilac_items([{
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
    }])

    # Select multiple signal leafs with aliasing.
    result = db.select_rows([
      'str',
      Column((LILAC_COLUMN, 'str', 'test_signal', 'flen'), alias='flen'),
      Column((LILAC_COLUMN, 'str', 'test_signal', 'len'), alias='len')
    ])

    assert list(result) == lilac_items([{
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
    }])

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
      }])
    test_signal_a = TestParamSignal(param='a')
    test_signal_b = TestParamSignal(param='b')
    db.compute_signal(test_signal_a, 'text')
    db.compute_signal(test_signal_b, 'text')

    assert db.manifest() == DatasetManifest(
      namespace=TEST_NAMESPACE,
      dataset_name=TEST_DATASET_NAME,
      data_schema=schema({
        UUID_COLUMN: 'string',
        'text': 'string',
        LILAC_COLUMN: {
          'text': {
            'param_signal(param=a)': signal_field('string'),
            'param_signal(param=b)': signal_field('string'),
          }
        }
      }),
      num_items=2)

    result = db.select_rows(['text', LILAC_COLUMN])
    assert list(result) == lilac_items([{
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
    }])

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
      }])

    db.compute_signal(TestEmbedding(), 'text')
    db.compute_signal(TestEmbeddingSumSignal(), (LILAC_COLUMN, 'text', 'test_embedding'))

    emb_field = Field(
      dtype=DataType.EMBEDDING,
      fields={SIGNAL_METADATA_KEY: field({'neg_sum': 'float32'})},
      signal_root=True)

    emb_field.fields['test_embedding_sum'] = signal_field('float32')  # type: ignore
    assert db.manifest() == DatasetManifest(
      namespace=TEST_NAMESPACE,
      dataset_name=TEST_DATASET_NAME,
      data_schema=schema({
        UUID_COLUMN: 'string',
        'text': 'string',
        LILAC_COLUMN: {
          'text': {
            'test_embedding': emb_field
          },
        }
      }),
      num_items=2)

    result = db.select_rows()
    expected_result = lilac_items([{
      UUID_COLUMN: '1',
      'text': 'hello.',
      LILAC_COLUMN: {
        'text': {
          'test_embedding': lilac_item(
            None, {
              SIGNAL_METADATA_KEY: {
                'neg_sum': -1.0
              },
              'test_embedding_sum': 1.0
            },
            allow_none_value=True)
        }
      }
    }, {
      UUID_COLUMN: '2',
      'text': 'hello2.',
      LILAC_COLUMN: {
        'text': {
          'test_embedding': lilac_item(
            None, {
              SIGNAL_METADATA_KEY: {
                'neg_sum': -2.0
              },
              'test_embedding_sum': 2.0
            },
            allow_none_value=True)
        }
      }
    }])
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
      }])

    split_signal = TestSplitSignal()
    db.compute_signal(split_signal, 'text')
    db.compute_signal(TestEmbedding(), (LILAC_COLUMN, 'text', 'test_split_len', '*'))
    db.compute_signal(TestEmbeddingSumSignal(),
                      (LILAC_COLUMN, 'text', 'test_split_len', '*', 'test_embedding'))

    emb_field = Field(
      dtype=DataType.EMBEDDING,
      fields={SIGNAL_METADATA_KEY: field({'neg_sum': 'float32'})},
      signal_root=True)
    emb_field.fields['test_embedding_sum'] = signal_field('float32')  # type: ignore

    text_field = Field(
      dtype=DataType.STRING_SPAN, fields={SIGNAL_METADATA_KEY: field({'len': 'int32'})})
    text_field.fields['test_embedding'] = emb_field  # type: ignore

    assert db.manifest() == DatasetManifest(
      namespace=TEST_NAMESPACE,
      dataset_name=TEST_DATASET_NAME,
      data_schema=schema({
        UUID_COLUMN: 'string',
        'text': 'string',
        LILAC_COLUMN: {
          'text': {
            'test_split_len': signal_field([text_field])
          }
        }
      }),
      num_items=2)

    result = db.select_rows(
      ['text', Column((LILAC_COLUMN, 'text', 'test_split_len'), alias='sentences')])

    assert list(result) == lilac_items([{
      UUID_COLUMN: '1',
      'text': 'hello. hello2.',
      'sentences': [
        lilac_item(
          lilac_span(0, 6), {
            SIGNAL_METADATA_KEY: {
              'len': 6
            },
            'test_embedding': lilac_item(
              None, {
                SIGNAL_METADATA_KEY: {
                  'neg_sum': -1.0
                },
                'test_embedding_sum': 1.0
              },
              allow_none_value=True),
          }),
        lilac_item(
          lilac_span(7, 14), {
            SIGNAL_METADATA_KEY: {
              'len': 7
            },
            'test_embedding': lilac_item(
              None, {
                SIGNAL_METADATA_KEY: {
                  'neg_sum': -2.0
                },
                'test_embedding_sum': 2.0
              },
              allow_none_value=True),
          }),
      ]
    }, {
      UUID_COLUMN: '2',
      'text': 'hello world. hello world2.',
      'sentences': [
        lilac_item(
          lilac_span(0, 12), {
            SIGNAL_METADATA_KEY: {
              'len': 12
            },
            'test_embedding': lilac_item(
              None, {
                SIGNAL_METADATA_KEY: {
                  'neg_sum': -3.0
                },
                'test_embedding_sum': 3.0
              },
              allow_none_value=True),
          }),
        lilac_item(
          lilac_span(13, 26), {
            SIGNAL_METADATA_KEY: {
              'len': 13
            },
            'test_embedding': lilac_item(
              None, {
                SIGNAL_METADATA_KEY: {
                  'neg_sum': -4.0
                },
                'test_embedding_sum': 4.0
              },
              allow_none_value=True),
          })
      ]
    }])

  def test_split_signal(self, tmp_path: pathlib.Path, db_cls: Type[DatasetDB]) -> None:
    db = make_db(
      db_cls=db_cls,
      tmp_path=tmp_path,
      items=[{
        UUID_COLUMN: '1',
        'text': '[1, 1] first sentence. [1, 1] second sentence.',
      }, {
        UUID_COLUMN: '2',
        'text': 'b2 [2, 1] first sentence. [2, 1] second sentence.',
      }])

    signal = TestSplitSignal()
    db.compute_signal(signal, 'text')

    assert db.manifest() == DatasetManifest(
      namespace=TEST_NAMESPACE,
      dataset_name=TEST_DATASET_NAME,
      data_schema=schema({
        UUID_COLUMN: 'string',
        'text': 'string',
        LILAC_COLUMN: {
          'text': {
            'test_split_len': signal_field([
              Field(
                dtype=DataType.STRING_SPAN,
                fields={SIGNAL_METADATA_KEY: field({'len': field('int32')})})
            ])
          }
        },
      }),
      num_items=2)

    result = db.select_rows(['text', (LILAC_COLUMN, 'text', 'test_split_len')])
    expected_result = lilac_items([{
      UUID_COLUMN: '1',
      'text': '[1, 1] first sentence. [1, 1] second sentence.',
      f'{LILAC_COLUMN}.text.test_split_len': [
        signal_item(lilac_span(0, 22), {'len': 22}),
        signal_item(lilac_span(23, 46), {'len': 23}),
      ]
    }, {
      UUID_COLUMN: '2',
      'text': 'b2 [2, 1] first sentence. [2, 1] second sentence.',
      f'{LILAC_COLUMN}.text.test_split_len': [
        signal_item(lilac_span(0, 25), {'len': 25}),
        signal_item(lilac_span(26, 49), {'len': 23}),
      ]
    }])
    assert list(result) == expected_result

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
      }])
    test_signal = TestSignal()
    # Run the signal on the repeated field.
    db.compute_signal(test_signal, ('text', '*'))

    # Check the enriched dataset manifest has 'text' enriched.
    assert db.manifest() == DatasetManifest(
      namespace=TEST_NAMESPACE,
      dataset_name=TEST_DATASET_NAME,
      data_schema=schema({
        UUID_COLUMN: 'string',
        'text': ['string'],
        LILAC_COLUMN: {
          'text': [{
            'test_signal': signal_field({
              'len': 'int32',
              'flen': 'float32'
            })
          }]
        }
      }),
      num_items=2)

    result = db.select_rows([(LILAC_COLUMN, 'text', '*')])

    assert list(result) == lilac_items([{
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
    }])

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
      }])

    db.compute_signal(TestSplitterWithLen(), 'text')

    result = db.select_rows(['text', (LILAC_COLUMN, 'text', 'test_splitter_len')])
    expected_result = lilac_items([{
      UUID_COLUMN: '1',
      'text': '[1, 1] first sentence. [1, 1] second sentence.',
      f'{LILAC_COLUMN}.text.test_splitter_len': [
        signal_item(lilac_span(0, 22), {'len': 22}),
        signal_item(lilac_span(23, 46), {'len': 23}),
      ]
    }, {
      UUID_COLUMN: '2',
      'text': 'b2 [2, 1] first sentence. [2, 1] second sentence.',
      f'{LILAC_COLUMN}.text.test_splitter_len': [
        signal_item(lilac_span(0, 25), {'len': 25}),
        signal_item(lilac_span(26, 49), {'len': 23}),
      ]
    }])
    assert list(result) == expected_result
