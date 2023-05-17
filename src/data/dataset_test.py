"""Implementation-agnostic tests of the Dataset DB API."""

from typing import Iterable, Optional, cast

import numpy as np
import pytest
from typing_extensions import override

from ..schema import (
  UUID_COLUMN,
  VALUE_KEY,
  Field,
  Item,
  RichData,
  SignalOut,
  field,
  schema,
  signal_field,
)
from ..signals.signal import TextEmbeddingSignal, TextSignal, clear_signal_registry, register_signal
from .dataset import Column, DatasetManifest, val
from .dataset_test_utils import TEST_DATASET_NAME, TEST_NAMESPACE, TestDataMaker
from .dataset_utils import lilac_item, lilac_items, signal_item

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

EMBEDDINGS: list[tuple[str, list[float]]] = [('hello.', [1.0, 0.0, 0.0]),
                                             ('hello2.', [1.0, 1.0, 0.0]),
                                             ('hello world.', [1.0, 1.0, 1.0]),
                                             ('hello world2.', [2.0, 1.0, 1.0])]

STR_EMBEDDINGS: dict[str, list[float]] = {text: embedding for text, embedding in EMBEDDINGS}


class TestEmbedding(TextEmbeddingSignal):
  """A test embed function."""
  name = 'test_embedding'

  @override
  def fields(self) -> Field:
    """Return the fields for the embedding."""
    return signal_field(dtype='embedding', metadata={'neg_sum': 'float32'})

  @override
  def compute(self, data: Iterable[RichData]) -> Iterable[Item]:
    """Call the embedding function."""
    embeddings = [np.array(STR_EMBEDDINGS[cast(str, example)]) for example in data]
    yield from (signal_item(e, metadata={'neg_sum': -1 * e.sum()}) for e in embeddings)


class LengthSignal(TextSignal):
  name = 'length_signal'

  _call_count: int = 0

  def fields(self) -> Field:
    return field('int32')

  def compute(self, data: Iterable[RichData]) -> Iterable[Optional[SignalOut]]:
    for text_content in data:
      self._call_count += 1
      yield len(text_content)


class TestSignal(TextSignal):
  name = 'test_signal'

  @override
  def fields(self) -> Field:
    return field({'len': 'int32', 'flen': 'float32'})

  @override
  def compute(self, data: Iterable[RichData]) -> Iterable[Optional[Item]]:
    return [{'len': len(text_content), 'flen': float(len(text_content))} for text_content in data]


@pytest.fixture(scope='module', autouse=True)
def setup_teardown() -> Iterable[None]:
  # Setup.
  register_signal(TestSignal)
  register_signal(LengthSignal)

  # Unit test runs.
  yield

  # Teardown.
  clear_signal_registry()


def test_select_all_columns(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data(SIMPLE_ITEMS)

  result = dataset.select_rows()
  assert list(result) == lilac_items(SIMPLE_ITEMS)


def test_select_subcols_with_dot_seperator(make_test_data: TestDataMaker) -> None:
  items: list[Item] = [{
    UUID_COLUMN: '1',
    'people': [{
      'name': 'A',
      'address': {
        'zip': 1
      }
    }, {
      'name': 'B',
      'address': {
        'zip': 2
      }
    }]
  }, {
    UUID_COLUMN: '2',
    'people': [{
      'name': 'C',
      'address': {
        'zip': 3
      }
    }]
  }]
  dataset = make_test_data(items)

  result = dataset.select_rows(['people.*.name', 'people.*.address.zip'])
  assert list(result) == lilac_items([{
    UUID_COLUMN: '1',
    'people.*.name': ['A', 'B'],
    'people.*.address.zip': [1, 2]
  }, {
    UUID_COLUMN: '2',
    'people.*.name': ['C'],
    'people.*.address.zip': [3]
  }])

  result = dataset.select_rows(['people.*.address.zip'], combine_columns=True)
  assert list(result) == lilac_items([{
    UUID_COLUMN: '1',
    'people': [{
      'address': {
        'zip': 1
      }
    }, {
      'address': {
        'zip': 2
      }
    }]
  }, {
    UUID_COLUMN: '2',
    'people': [{
      'address': {
        'zip': 3
      }
    }]
  }])

  result = dataset.select_rows(['people'])
  assert list(result) == lilac_items(items)


def test_select_subcols_with_escaped_dot(make_test_data: TestDataMaker) -> None:
  items: list[Item] = [{
    UUID_COLUMN: '1',
    'people.new': [{
      'name': 'A'
    }, {
      'name': 'B'
    }]
  }, {
    UUID_COLUMN: '2',
    'people.new': [{
      'name': 'C'
    }]
  }]
  dataset = make_test_data(items)

  result = dataset.select_rows(['"people.new".*.name'])
  assert list(result) == lilac_items([{
    UUID_COLUMN: '1',
    'people.new.*.name': ['A', 'B'],
  }, {
    UUID_COLUMN: '2',
    'people.new.*.name': ['C'],
  }])

  # Escape name even though it does not need to be.
  result = dataset.select_rows(['"people.new".*."name"'])
  assert list(result) == lilac_items([{
    UUID_COLUMN: '1',
    'people.new.*.name': ['A', 'B'],
  }, {
    UUID_COLUMN: '2',
    'people.new.*.name': ['C'],
  }])


def test_select_star(make_test_data: TestDataMaker) -> None:
  items: list[Item] = [{
    UUID_COLUMN: '1',
    'name': 'A',
    'info': {
      'age': 40
    }
  }, {
    UUID_COLUMN: '2',
    'name': 'B',
    'info': {
      'age': 42
    }
  }]
  dataset = make_test_data(items)

  # Select *.
  result = dataset.select_rows(['*'])
  assert list(result) == lilac_items(items)

  # Select (*,).
  result = dataset.select_rows([('*',)])
  assert list(result) == lilac_items(items)

  # Select *, plus a redundant `info` column.
  result = dataset.select_rows(['*', 'info'])
  assert list(result) == lilac_items([{
    UUID_COLUMN: '1',
    'name': 'A',
    'info': {
      'age': 40
    },
    'info_2': {
      'age': 40
    },
  }, {
    UUID_COLUMN: '2',
    'name': 'B',
    'info': {
      'age': 42
    },
    'info_2': {
      'age': 42
    },
  }])

  # Select * plus an inner `info.age` column.
  result = dataset.select_rows(['*', ('info', 'age')])
  assert list(result) == lilac_items([{
    UUID_COLUMN: '1',
    'name': 'A',
    'info': {
      'age': 40
    },
    'info.age': 40
  }, {
    UUID_COLUMN: '2',
    'name': 'B',
    'info': {
      'age': 42
    },
    'info.age': 42
  }])


def test_select_star_with_combine_cols(make_test_data: TestDataMaker) -> None:
  items: list[Item] = [{
    UUID_COLUMN: '1',
    'name': 'A',
    'info': {
      'age': 40
    }
  }, {
    UUID_COLUMN: '2',
    'name': 'B',
    'info': {
      'age': 42
    }
  }]
  dataset = make_test_data(items)

  # Select *.
  result = dataset.select_rows(['*'], combine_columns=True)
  assert list(result) == lilac_items(items)

  # Select *, plus a redundant `info` column.
  result = dataset.select_rows(['*', 'info'], combine_columns=True)
  assert list(result) == lilac_items(items)

  # Select * plus an inner `info.age` column.
  result = dataset.select_rows(['*', ('info', 'age')], combine_columns=True)
  assert list(result) == lilac_items(items)

  # Select *, plus redundant `name`, plus a udf.
  udf = Column('name', signal_udf=TestSignal())
  result = dataset.select_rows(['*', 'name', udf], combine_columns=True)
  assert list(result) == lilac_items([{
    UUID_COLUMN: '1',
    'name': lilac_item('A', {'test_signal': {
      'len': 1,
      'flen': 1.0
    }}),
    'info': {
      'age': 40
    }
  }, {
    UUID_COLUMN: '2',
    'name': lilac_item('B', {'test_signal': {
      'len': 1,
      'flen': 1.0
    }}),
    'info': {
      'age': 42
    }
  }])


def test_select_ids(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data(SIMPLE_ITEMS)

  result = dataset.select_rows([UUID_COLUMN])

  assert list(result) == [{UUID_COLUMN: '1'}, {UUID_COLUMN: '2'}, {UUID_COLUMN: '3'}]


def test_select_ids_with_limit_and_offset(make_test_data: TestDataMaker) -> None:
  items: list[Item] = [{UUID_COLUMN: str(i)} for i in range(10, 20)]
  dataset = make_test_data(items)

  result = dataset.select_rows([UUID_COLUMN], offset=1, limit=3)
  assert list(result) == [{UUID_COLUMN: '11'}, {UUID_COLUMN: '12'}, {UUID_COLUMN: '13'}]

  result = dataset.select_rows([UUID_COLUMN], offset=7, limit=2)
  assert list(result) == [{UUID_COLUMN: '17'}, {UUID_COLUMN: '18'}]

  result = dataset.select_rows([UUID_COLUMN], offset=9, limit=200)
  assert list(result) == [{UUID_COLUMN: '19'}]

  result = dataset.select_rows([UUID_COLUMN], offset=10, limit=200)
  assert list(result) == []


def test_columns(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data(SIMPLE_ITEMS)

  result = dataset.select_rows(['str', 'float'])

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


def test_merge_values(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data([{
    UUID_COLUMN: '1',
    'text': 'hello'
  }, {
    UUID_COLUMN: '2',
    'text': 'everybody'
  }])
  test_signal = TestSignal()
  dataset.compute_signal(test_signal, 'text')
  length_signal = LengthSignal()
  dataset.compute_signal(length_signal, 'text')

  result = dataset.select_rows(['text'])
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
  result = dataset.select_rows(
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
  result = dataset.select_rows(
    ['text', ('text', 'test_signal', 'flen'), ('text', 'test_signal', 'len')], combine_columns=True)
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
  result = dataset.select_rows(
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

  result = dataset.select_rows(columns=[Column(('text'), alias='text_enrichment')])
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


def test_merge_array_values(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data([{
    UUID_COLUMN: '1',
    'texts': ['hello', 'everybody']
  }, {
    UUID_COLUMN: '2',
    'texts': ['a', 'bc', 'def']
  }])

  test_signal = TestSignal()
  dataset.compute_signal(test_signal, ('texts', '*'))
  length_signal = LengthSignal()
  dataset.compute_signal(length_signal, ('texts', '*'))

  assert dataset.manifest() == DatasetManifest(
    namespace=TEST_NAMESPACE,
    dataset_name=TEST_DATASET_NAME,
    data_schema=schema({
      UUID_COLUMN: 'string',
      'texts': [
        field(
          {
            'length_signal': signal_field(dtype='int32', signal=length_signal.dict()),
            'test_signal': signal_field(
              fields={
                'len': 'int32',
                'flen': 'float32'
              }, signal=test_signal.dict())
          },
          dtype='string')
      ],
    }),
    num_items=2)

  result = dataset.select_rows(['texts'])
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
  result = dataset.select_rows(
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


def test_combining_columns(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data([{
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
  result = dataset.select_rows(['text', ('extra', 'text', 'test_signal')], combine_columns=True)
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
  result = dataset.select_rows(['text', ('extra', 'text', 'length_signal')], combine_columns=True)
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
  result = dataset.select_rows([('extra', 'text', 'length_signal')], combine_columns=True)
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
  result = dataset.select_rows([len_col], combine_columns=True)
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
  udf_col = Column('text', alias='ignored', signal_udf=LengthSignal())
  result = dataset.select_rows(['text', udf_col], combine_columns=True)
  assert list(result) == lilac_items([{
    UUID_COLUMN: '1',
    'text': lilac_item('hello', {'length_signal': 5})
  }, {
    UUID_COLUMN: '2',
    'text': lilac_item('everybody', {'length_signal': 9})
  }])


def test_source_joined_with_named_signal_column(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data(SIMPLE_ITEMS)
  assert dataset.manifest() == DatasetManifest(
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
  dataset.compute_signal(test_signal, 'str')

  # Check the enriched dataset manifest has 'text' enriched.
  assert dataset.manifest() == DatasetManifest(
    namespace=TEST_NAMESPACE,
    dataset_name=TEST_DATASET_NAME,
    data_schema=schema({
      UUID_COLUMN: 'string',
      'str': field(
        {
          'test_signal': signal_field(
            fields={
              'len': 'int32',
              'flen': 'float32'
            }, signal=test_signal.dict())
        },
        dtype='string'),
      'int': 'int32',
      'bool': 'boolean',
      'float': 'float32',
    }),
    num_items=3)

  # Select both columns, without val() on str.
  result = dataset.select_rows(['str', Column(('str', 'test_signal'), alias='test_signal_on_str')])

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
  result = dataset.select_rows(
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


def test_invalid_column_paths(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data([{
    UUID_COLUMN: '1',
    'text': lilac_item('hello', {'test_signal': {
      'len': 5
    }}),
    'text2': [
      lilac_item('hello', {'test_signal': {
        'len': 5
      }}),
      lilac_item('hi', {'test_signal': {
        'len': 2
      }})
    ],
  }])

  with pytest.raises(ValueError, match='Path part "invalid" not found in the dataset'):
    dataset.select_rows([('text', 'test_signal', 'invalid')])

  with pytest.raises(ValueError, match='Selecting a specific index of a repeated field'):
    dataset.select_rows([('text2', '4', 'test_signal')])
