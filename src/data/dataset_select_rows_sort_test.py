"""Tests for dataset.select_rows(sort_by=...)."""

from typing import Iterable, Optional

import pytest

from ..schema import UUID_COLUMN, Field, RichData, SignalOut, field
from ..signals.signal import TextSignal, clear_signal_registry, register_signal
from .dataset import Column, SortOrder
from .dataset_test_utils import TestDataMaker
from .dataset_utils import lilac_item, lilac_items


def test_sort_by_source_no_alias_no_repeated(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data([{
    UUID_COLUMN: '1',
    'erased': True,
    'score': 4.1,
    'document': {
      'num_pages': 4,
      'header': {
        'title': 'c'
      }
    }
  }, {
    UUID_COLUMN: '2',
    'erased': False,
    'score': 3.5,
    'document': {
      'num_pages': 5,
      'header': {
        'title': 'b'
      }
    },
  }, {
    UUID_COLUMN: '3',
    'erased': True,
    'score': 3.7,
    'document': {
      'num_pages': 3,
      'header': {
        'title': 'a'
      }
    },
  }])

  # Sort by bool.
  result = dataset.select_rows(columns=[UUID_COLUMN], sort_by=['erased'], sort_order=SortOrder.ASC)
  assert list(result) == [{UUID_COLUMN: '2'}, {UUID_COLUMN: '1'}, {UUID_COLUMN: '3'}]
  result = dataset.select_rows(columns=[UUID_COLUMN], sort_by=['erased'], sort_order=SortOrder.DESC)
  assert list(result) == [{UUID_COLUMN: '1'}, {UUID_COLUMN: '3'}, {UUID_COLUMN: '2'}]

  # Sort by float.
  result = dataset.select_rows(columns=[UUID_COLUMN], sort_by=['score'], sort_order=SortOrder.ASC)
  assert list(result) == [{UUID_COLUMN: '2'}, {UUID_COLUMN: '3'}, {UUID_COLUMN: '1'}]
  result = dataset.select_rows(columns=[UUID_COLUMN], sort_by=['score'], sort_order=SortOrder.DESC)
  assert list(result) == [{UUID_COLUMN: '1'}, {UUID_COLUMN: '3'}, {UUID_COLUMN: '2'}]

  # Sort by nested int.
  result = dataset.select_rows(
    columns=[UUID_COLUMN], sort_by=['document.num_pages'], sort_order=SortOrder.ASC)
  assert list(result) == [{UUID_COLUMN: '3'}, {UUID_COLUMN: '1'}, {UUID_COLUMN: '2'}]
  result = dataset.select_rows(
    columns=[UUID_COLUMN], sort_by=['document.num_pages'], sort_order=SortOrder.DESC)
  assert list(result) == [{UUID_COLUMN: '2'}, {UUID_COLUMN: '1'}, {UUID_COLUMN: '3'}]

  # Sort by double nested string.
  result = dataset.select_rows(
    columns=[UUID_COLUMN], sort_by=['document.header.title'], sort_order=SortOrder.ASC)
  assert list(result) == [{UUID_COLUMN: '3'}, {UUID_COLUMN: '2'}, {UUID_COLUMN: '1'}]
  result = dataset.select_rows(
    columns=[UUID_COLUMN], sort_by=['document.header.title'], sort_order=SortOrder.DESC)
  assert list(result) == [{UUID_COLUMN: '1'}, {UUID_COLUMN: '2'}, {UUID_COLUMN: '3'}]


class TestSignal(TextSignal):
  name = 'test_signal'

  def fields(self) -> Field:
    return field({'len': 'int32', 'is_all_cap': 'boolean'})

  def compute(self, data: Iterable[RichData]) -> Iterable[Optional[SignalOut]]:
    for text_content in data:
      yield {'len': len(text_content), 'is_all_cap': text_content.isupper()}


class TestPrimitiveSignal(TextSignal):
  name = 'primitive_signal'

  def fields(self) -> Field:
    return field('int32')

  def compute(self, data: Iterable[RichData]) -> Iterable[Optional[SignalOut]]:
    for text_content in data:
      yield len(text_content) + 1


@pytest.fixture(scope='module', autouse=True)
def setup_teardown() -> Iterable[None]:
  # Setup.
  register_signal(TestSignal)
  register_signal(TestPrimitiveSignal)
  # Unit test runs.
  yield
  # Teardown.
  clear_signal_registry()


def test_sort_by_signal_no_alias_no_repeated(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data([{
    UUID_COLUMN: '1',
    'text': 'HEY'
  }, {
    UUID_COLUMN: '2',
    'text': 'everyone'
  }, {
    UUID_COLUMN: '3',
    'text': 'HI'
  }])

  dataset.compute_signal(TestSignal(), 'text')

  # Sort by `signal.len`.
  result = dataset.select_rows(
    columns=[UUID_COLUMN], sort_by=['text.test_signal.len'], sort_order=SortOrder.ASC)
  assert list(result) == [{UUID_COLUMN: '3'}, {UUID_COLUMN: '1'}, {UUID_COLUMN: '2'}]
  result = dataset.select_rows(
    columns=[UUID_COLUMN], sort_by=['text.test_signal.len'], sort_order=SortOrder.DESC)
  assert list(result) == [{UUID_COLUMN: '2'}, {UUID_COLUMN: '1'}, {UUID_COLUMN: '3'}]

  # Sort by `signal.is_all_cap`.
  result = dataset.select_rows(
    columns=[UUID_COLUMN], sort_by=['text.test_signal.is_all_cap'], sort_order=SortOrder.ASC)
  assert list(result) == [{UUID_COLUMN: '2'}, {UUID_COLUMN: '1'}, {UUID_COLUMN: '3'}]
  result = dataset.select_rows(
    columns=[UUID_COLUMN], sort_by=['text.test_signal.is_all_cap'], sort_order=SortOrder.DESC)
  assert list(result) == [{UUID_COLUMN: '1'}, {UUID_COLUMN: '3'}, {UUID_COLUMN: '2'}]


def test_sort_by_signal_alias_no_repeated(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data([{
    UUID_COLUMN: '1',
    'text': 'HEY'
  }, {
    UUID_COLUMN: '2',
    'text': 'everyone'
  }, {
    UUID_COLUMN: '3',
    'text': 'HI'
  }])

  dataset.compute_signal(TestSignal(), 'text')

  # Sort by `signal.len`.
  signal_alias = Column('text.test_signal', alias='signal')
  result = dataset.select_rows(
    columns=[signal_alias], sort_by=['signal.len'], sort_order=SortOrder.ASC)
  assert list(result) == lilac_items([{
    UUID_COLUMN: '3',
    'signal': {
      'len': 2,
      'is_all_cap': True
    }
  }, {
    UUID_COLUMN: '1',
    'signal': {
      'len': 3,
      'is_all_cap': True
    }
  }, {
    UUID_COLUMN: '2',
    'signal': {
      'len': 8,
      'is_all_cap': False
    }
  }])
  result = dataset.select_rows(
    columns=[signal_alias], sort_by=['signal.len'], sort_order=SortOrder.DESC)
  assert list(result) == lilac_items([{
    UUID_COLUMN: '2',
    'signal': {
      'len': 8,
      'is_all_cap': False
    }
  }, {
    UUID_COLUMN: '1',
    'signal': {
      'len': 3,
      'is_all_cap': True
    }
  }, {
    UUID_COLUMN: '3',
    'signal': {
      'len': 2,
      'is_all_cap': True
    }
  }])


def test_sort_by_enriched_alias_no_repeated(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data([{
    UUID_COLUMN: '1',
    'text': 'HEY'
  }, {
    UUID_COLUMN: '2',
    'text': 'everyone'
  }, {
    UUID_COLUMN: '3',
    'text': 'HI'
  }])

  dataset.compute_signal(TestSignal(), 'text')

  # Sort by `document.test_signal.is_all_cap` where 'document' is an alias to 'text'.
  text_alias = Column('text', alias='document')
  result = dataset.select_rows(
    columns=[text_alias], sort_by=['document.test_signal.is_all_cap'], sort_order=SortOrder.ASC)
  assert list(result) == lilac_items([{
    UUID_COLUMN: '2',
    'document': lilac_item('everyone', {'test_signal': {
      'len': 8,
      'is_all_cap': False
    }})
  }, {
    UUID_COLUMN: '1',
    'document': lilac_item('HEY', {'test_signal': {
      'len': 3,
      'is_all_cap': True
    }})
  }, {
    UUID_COLUMN: '3',
    'document': lilac_item('HI', {'test_signal': {
      'len': 2,
      'is_all_cap': True
    }})
  }])

  result = dataset.select_rows(
    columns=[text_alias], sort_by=['document.test_signal.is_all_cap'], sort_order=SortOrder.DESC)
  assert list(result) == lilac_items([{
    UUID_COLUMN: '1',
    'document': lilac_item('HEY', {'test_signal': {
      'len': 3,
      'is_all_cap': True
    }})
  }, {
    UUID_COLUMN: '3',
    'document': lilac_item('HI', {'test_signal': {
      'len': 2,
      'is_all_cap': True
    }})
  }, {
    UUID_COLUMN: '2',
    'document': lilac_item('everyone', {'test_signal': {
      'len': 8,
      'is_all_cap': False
    }})
  }])


def test_sort_by_udf_alias_no_repeated(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data([{
    UUID_COLUMN: '1',
    'text': 'HEY'
  }, {
    UUID_COLUMN: '2',
    'text': 'everyone'
  }, {
    UUID_COLUMN: '3',
    'text': 'HI'
  }])

  # Equivalent to: SELECT `TestSignal(text) AS udf`.
  text_udf = Column('text', signal_udf=TestSignal(), alias='udf')
  # Sort by `udf.len`, where `udf` is an alias to `TestSignal(text)`.
  result = dataset.select_rows(['*', text_udf], sort_by=['udf.len'], sort_order=SortOrder.ASC)
  assert list(result) == lilac_items([{
    UUID_COLUMN: '3',
    'text': 'HI',
    'udf': {
      'len': 2,
      'is_all_cap': True
    }
  }, {
    UUID_COLUMN: '1',
    'text': 'HEY',
    'udf': {
      'len': 3,
      'is_all_cap': True
    }
  }, {
    UUID_COLUMN: '2',
    'text': 'everyone',
    'udf': {
      'len': 8,
      'is_all_cap': False
    }
  }])


def test_sort_by_primitive_udf_alias_no_repeated(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data([{
    UUID_COLUMN: '1',
    'text': 'HEY'
  }, {
    UUID_COLUMN: '2',
    'text': 'everyone'
  }, {
    UUID_COLUMN: '3',
    'text': 'HI'
  }])

  # Equivalent to: SELECT `TestSignal(text) AS udf`.
  text_udf = Column('text', signal_udf=TestPrimitiveSignal(), alias='udf')
  # Sort by the primitive value returned by the udf.
  result = dataset.select_rows(['*', text_udf], sort_by=['udf'], sort_order=SortOrder.ASC)
  assert list(result) == lilac_items([{
    UUID_COLUMN: '3',
    'text': 'HI',
    'udf': 3
  }, {
    UUID_COLUMN: '1',
    'text': 'HEY',
    'udf': 4
  }, {
    UUID_COLUMN: '2',
    'text': 'everyone',
    'udf': 9
  }])


def test_sort_by_source_non_leaf_errors(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data([{
    UUID_COLUMN: '1',
    'vals': [7, 1]
  }, {
    UUID_COLUMN: '2',
    'vals': [3, 4]
  }, {
    UUID_COLUMN: '3',
    'vals': [9, 0]
  }])

  # Sort by repeated.
  with pytest.raises(ValueError, match='Can not sort by .* since it is not a leaf field'):
    dataset.select_rows(columns=[UUID_COLUMN], sort_by=['vals'], sort_order=SortOrder.ASC)


def test_sort_by_source_repeated_not_supported(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data([{
    UUID_COLUMN: '1',
    'vals': [7, 1]
  }, {
    UUID_COLUMN: '2',
    'vals': [3, 4]
  }, {
    UUID_COLUMN: '3',
    'vals': [9, 0]
  }])

  # Sort by repeated.
  with pytest.raises(
      NotImplementedError, match='Can not sort .* since repeated fields are not yet supported'):
    dataset.select_rows(columns=[UUID_COLUMN], sort_by=['vals.*'], sort_order=SortOrder.ASC)
