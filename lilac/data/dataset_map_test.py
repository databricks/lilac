"""Tests for dataset.map()."""

import inspect
from datetime import datetime
from typing import ClassVar, Iterable, Optional

import pytest
from freezegun import freeze_time
from typing_extensions import override

from ..schema import PATH_WILDCARD, VALUE_KEY, Field, Item, MapInfo, RichData, field, schema
from ..signal import TextSignal, clear_signal_registry, register_signal
from ..sources.source_registry import clear_source_registry, register_source
from .dataset import DatasetManifest
from .dataset_test_utils import (
  TEST_DATASET_NAME,
  TEST_NAMESPACE,
  TestDataMaker,
  TestSource,
  enriched_item,
)

TEST_TIME = datetime(2023, 8, 15, 1, 23, 45)


class TestFirstCharSignal(TextSignal):
  name: ClassVar[str] = 'test_signal'

  @override
  def fields(self) -> Field:
    return field(fields={'len': 'int32', 'firstchar': 'string'})

  @override
  def compute(self, data: Iterable[RichData]) -> Iterable[Optional[Item]]:
    return [{'len': len(text_content), 'firstchar': text_content[0]} for text_content in data]


@pytest.fixture(scope='module', autouse=True)
def setup_teardown() -> Iterable[None]:
  # Setup.
  clear_signal_registry()
  register_source(TestSource)
  register_signal(TestFirstCharSignal)

  # Unit test runs.
  yield
  # Teardown.
  clear_source_registry()
  clear_signal_registry()


@freeze_time(TEST_TIME)
def test_map(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data([{'text': 'a sentence'}, {'text': 'b sentence'}])

  signal = TestFirstCharSignal()
  dataset.compute_signal(signal, 'text')

  def _map_fn(row: Item) -> Item:
    return {'result': f'{row["text.test_signal"]["firstchar"]}_{len(row["text"])}'}

  # Write the output to a new column.
  dataset.map(_map_fn, output_path='output_text', combine_columns=False)

  assert dataset.manifest() == DatasetManifest(
    namespace=TEST_NAMESPACE,
    dataset_name=TEST_DATASET_NAME,
    data_schema=schema(
      {
        'text': field(
          'string',
          fields={
            'test_signal': field(
              fields={'len': 'int32', 'firstchar': 'string'}, signal={'signal_name': 'test_signal'}
            )
          },
        ),
        'output_text': field(
          fields={'result': 'string'},
          map=MapInfo(
            fn_name='_map_fn', fn_source=inspect.getsource(_map_fn), date_created=TEST_TIME
          ),
        ),
      }
    ),
    num_items=2,
    source=TestSource(),
  )

  rows = list(dataset.select_rows([PATH_WILDCARD]))
  assert rows == [
    {
      'text': 'a sentence',
      'text.test_signal': {'firstchar': 'a', 'len': 10},
      'output_text': {'result': 'a_10'},
    },
    {
      'text': 'b sentence',
      'text.test_signal': {'firstchar': 'b', 'len': 10},
      'output_text': {'result': 'b_10'},
    },
  ]


@freeze_time(TEST_TIME)
def test_map_continuation(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data([{'id': 0, 'text': 'a sentence'}, {'id': 1, 'text': 'b sentence'}])

  first_run = True
  map_call_ids = []

  def _map_fn(row: Item) -> Item:
    nonlocal first_run, map_call_ids
    map_call_ids.append(row['id'])

    if first_run and row['id'] == 1:
      raise ValueError('Throwing')

    return row['id']

  # Write the output to a new column.
  with pytest.raises(ValueError, match='Throwing'):
    dataset.map(_map_fn, output_path='map_id', combine_columns=False)

  # Map should be called twice. The second time it throws.
  assert map_call_ids == [0, 1]
  # The schema should not reflect the output of the map as it didn't finish.
  assert dataset.manifest() == DatasetManifest(
    namespace=TEST_NAMESPACE,
    dataset_name=TEST_DATASET_NAME,
    data_schema=schema({'text': 'string', 'id': 'int32'}),
    num_items=2,
    source=TestSource(),
  )
  # The rows should not reflect the output of the unfinished map.
  rows = list(dataset.select_rows([PATH_WILDCARD]))
  assert rows == [{'text': 'a sentence', 'id': 0}, {'text': 'b sentence', 'id': 1}]

  first_run = False
  map_call_ids = []
  dataset.map(_map_fn, output_path='map_id', combine_columns=False)

  # Map should only be called one more time for the remaining row id.
  assert map_call_ids == [1]

  assert dataset.manifest() == DatasetManifest(
    namespace=TEST_NAMESPACE,
    dataset_name=TEST_DATASET_NAME,
    data_schema=schema(
      {
        'text': 'string',
        'id': 'int32',
        'map_id': field(
          dtype='int64',
          map=MapInfo(
            fn_name='_map_fn', fn_source=inspect.getsource(_map_fn), date_created=TEST_TIME
          ),
        ),
      }
    ),
    num_items=2,
    source=TestSource(),
  )

  rows = list(dataset.select_rows([PATH_WILDCARD]))
  assert rows == [
    {'text': 'a sentence', 'id': 0, 'map_id': 0},
    {'text': 'b sentence', 'id': 1, 'map_id': 1},
  ]


@freeze_time(TEST_TIME)
def test_map_continuation_overwrite(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data([{'id': 0, 'text': 'a sentence'}, {'id': 1, 'text': 'b sentence'}])

  first_run = True
  map_call_ids = []

  def _map_fn(row: Item) -> Item:
    nonlocal first_run, map_call_ids
    map_call_ids.append(row['id'])

    if first_run and row['id'] == 1:
      raise ValueError('Throwing')

    return row['id']

  # Write the output to a new column.
  with pytest.raises(ValueError, match='Throwing'):
    dataset.map(_map_fn, output_path='map_id', combine_columns=False)

  # Map should be called twice. The second time it throws.
  assert map_call_ids == [0, 1]

  first_run = False
  map_call_ids = []
  dataset.map(_map_fn, output_path='map_id', combine_columns=False, overwrite=True)

  # Map should be called again for both ids.
  assert map_call_ids == [0, 1]

  assert dataset.manifest() == DatasetManifest(
    namespace=TEST_NAMESPACE,
    dataset_name=TEST_DATASET_NAME,
    data_schema=schema(
      {
        'text': 'string',
        'id': 'int32',
        'map_id': field(
          dtype='int64',
          map=MapInfo(
            fn_name='_map_fn', fn_source=inspect.getsource(_map_fn), date_created=TEST_TIME
          ),
        ),
      }
    ),
    num_items=2,
    source=TestSource(),
  )

  rows = list(dataset.select_rows([PATH_WILDCARD]))
  assert rows == [
    {'text': 'a sentence', 'id': 0, 'map_id': 0},
    {'text': 'b sentence', 'id': 1, 'map_id': 1},
  ]


@freeze_time(TEST_TIME)
def test_map_overwrite(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data([{'text': 'a'}, {'text': 'b'}])

  prefix = '0'

  def _map_fn(row: Item) -> Item:
    nonlocal prefix
    return prefix + row['text']

  # Write the output to a new column.
  dataset.map(_map_fn, output_path='map_text', combine_columns=False)

  rows = list(dataset.select_rows([PATH_WILDCARD]))
  assert rows == [{'text': 'a', 'map_text': '0a'}, {'text': 'b', 'map_text': '0b'}]

  with pytest.raises(ValueError, match=' which already exists in the dataset'):
    dataset.map(_map_fn, output_path='map_text', combine_columns=False)

  prefix = '1'
  # Overwrite the output
  dataset.map(_map_fn, output_path='map_text', combine_columns=False, overwrite=True)

  assert dataset.manifest() == DatasetManifest(
    namespace=TEST_NAMESPACE,
    dataset_name=TEST_DATASET_NAME,
    data_schema=schema(
      {
        'text': 'string',
        'map_text': field(
          dtype='string',
          map=MapInfo(
            fn_name='_map_fn', fn_source=inspect.getsource(_map_fn), date_created=TEST_TIME
          ),
        ),
      }
    ),
    num_items=2,
    source=TestSource(),
  )

  rows = list(dataset.select_rows([PATH_WILDCARD]))
  assert rows == [{'text': 'a', 'map_text': '1a'}, {'text': 'b', 'map_text': '1b'}]


@freeze_time(TEST_TIME)
def test_map_no_output_col(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data([{'text': 'a sentence'}, {'text': 'b sentence'}])

  signal = TestFirstCharSignal()
  dataset.compute_signal(signal, 'text')

  def _map_fn(row: Item) -> Item:
    return {'result': f'{row["text.test_signal"]["firstchar"]}_{len(row["text"])}'}

  dataset.map(_map_fn, combine_columns=False)

  # The manifest should contain no new columns.
  assert dataset.manifest() == DatasetManifest(
    namespace=TEST_NAMESPACE,
    dataset_name=TEST_DATASET_NAME,
    data_schema=schema(
      {
        'text': field(
          'string',
          fields={
            'test_signal': field(
              fields={'len': 'int32', 'firstchar': 'string'}, signal={'signal_name': 'test_signal'}
            )
          },
        )
      }
    ),
    num_items=2,
    source=TestSource(),
  )

  rows = list(dataset.select_rows([PATH_WILDCARD]))
  assert rows == [
    {'text': 'a sentence', 'text.test_signal': {'firstchar': 'a', 'len': 10}},
    {'text': 'b sentence', 'text.test_signal': {'firstchar': 'b', 'len': 10}},
  ]


@freeze_time(TEST_TIME)
def test_map_explicit_columns(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data([{'text': 'a sentence', 'extra': 1}, {'text': 'b sentence', 'extra': 2}])

  signal = TestFirstCharSignal()
  dataset.compute_signal(signal, 'text')

  def _map_fn(row: Item) -> Item:
    assert 'extra' not in row
    return {'result': f'{row["text.test_signal"]["firstchar"]}_{len(row["text"])}'}

  # Write the output to a new column.
  dataset.map(
    _map_fn,
    output_path='output_text',
    input_paths=[('text',), ('text', 'test_signal')],
    combine_columns=False,
  )

  assert dataset.manifest() == DatasetManifest(
    namespace=TEST_NAMESPACE,
    dataset_name=TEST_DATASET_NAME,
    data_schema=schema(
      {
        'text': field(
          'string',
          fields={
            'test_signal': field(
              fields={'len': 'int32', 'firstchar': 'string'}, signal={'signal_name': 'test_signal'}
            )
          },
        ),
        'extra': 'int32',
        'output_text': field(
          fields={'result': 'string'},
          map=MapInfo(
            fn_name='_map_fn', fn_source=inspect.getsource(_map_fn), date_created=TEST_TIME
          ),
        ),
      }
    ),
    num_items=2,
    source=TestSource(),
  )

  rows = list(dataset.select_rows([PATH_WILDCARD]))
  assert rows == [
    {
      'text': 'a sentence',
      'extra': 1,
      'text.test_signal': {'firstchar': 'a', 'len': 10},
      'output_text': {'result': 'a_10'},
    },
    {
      'text': 'b sentence',
      'extra': 2,
      'text.test_signal': {'firstchar': 'b', 'len': 10},
      'output_text': {'result': 'b_10'},
    },
  ]


@freeze_time(TEST_TIME)
def test_map_chained(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data([{'text': 'a sentence'}, {'text': 'b sentence'}])

  def _split_fn(row: Item) -> Item:
    return row['text'].split(' ')

  dataset.map(_split_fn, output_path='splits', combine_columns=False)

  def _rearrange_fn(row: Item) -> Item:
    return row['splits'][1] + ' ' + row['splits'][0]

  dataset.map(_rearrange_fn, output_path='rearrange', combine_columns=False)

  rows = list(dataset.select_rows([PATH_WILDCARD]))
  assert rows == [
    {'text': 'a sentence', 'splits': ['a', 'sentence'], 'rearrange': 'sentence a'},
    {'text': 'b sentence', 'splits': ['b', 'sentence'], 'rearrange': 'sentence b'},
  ]

  assert dataset.manifest() == DatasetManifest(
    namespace=TEST_NAMESPACE,
    dataset_name=TEST_DATASET_NAME,
    data_schema=schema(
      {
        'text': field('string'),
        'splits': field(
          fields=['string'],
          map=MapInfo(
            fn_name='_split_fn', fn_source=inspect.getsource(_split_fn), date_created=TEST_TIME
          ),
        ),
        'rearrange': field(
          'string',
          map=MapInfo(
            fn_name='_rearrange_fn',
            fn_source=inspect.getsource(_rearrange_fn),
            date_created=TEST_TIME,
          ),
        ),
      }
    ),
    num_items=2,
    source=TestSource(),
  )


@freeze_time(TEST_TIME)
def test_map_combine_columns(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data([{'text': 'a sentence'}, {'text': 'b sentence'}])

  signal = TestFirstCharSignal()
  dataset.compute_signal(signal, 'text')

  def _map_fn(row: Item) -> Item:
    # We use the combine_columns=True input here.
    return {'result': f'{row["text"]["test_signal"]["firstchar"]}_{len(row["text"][VALUE_KEY])}'}

  # Write the output to a new column.
  dataset.map(_map_fn, output_path='output_text', combine_columns=True)

  assert dataset.manifest() == DatasetManifest(
    namespace=TEST_NAMESPACE,
    dataset_name=TEST_DATASET_NAME,
    data_schema=schema(
      {
        'text': field(
          'string',
          fields={
            'test_signal': field(
              fields={'len': 'int32', 'firstchar': 'string'}, signal={'signal_name': 'test_signal'}
            )
          },
        ),
        'output_text': field(
          fields={'result': 'string'},
          map=MapInfo(
            fn_name='_map_fn', fn_source=inspect.getsource(_map_fn), date_created=TEST_TIME
          ),
        ),
      }
    ),
    num_items=2,
    source=TestSource(),
  )

  rows = list(dataset.select_rows([PATH_WILDCARD]))
  assert rows == [
    {
      'text': 'a sentence',
      'text.test_signal': {'firstchar': 'a', 'len': 10},
      'output_text': {'result': 'a_10'},
    },
    {
      'text': 'b sentence',
      'text.test_signal': {'firstchar': 'b', 'len': 10},
      'output_text': {'result': 'b_10'},
    },
  ]


@freeze_time(TEST_TIME)
def test_signal_on_map_output(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data([{'text': 'abcd'}, {'text': 'efghi'}])

  def _map_fn(row: Item) -> Item:
    return row['text'] + ' ' + row['text']

  dataset.map(_map_fn, output_path='double', combine_columns=False)

  # Compute a signal on the map output.
  signal = TestFirstCharSignal()
  dataset.compute_signal(signal, 'double')

  assert dataset.manifest() == DatasetManifest(
    namespace=TEST_NAMESPACE,
    dataset_name=TEST_DATASET_NAME,
    data_schema=schema(
      {
        'text': 'string',
        'double': field(
          'string',
          fields={
            'test_signal': field(
              fields={'len': 'int32', 'firstchar': 'string'}, signal={'signal_name': 'test_signal'}
            )
          },
          map=MapInfo(
            fn_name='_map_fn', fn_source=inspect.getsource(_map_fn), date_created=TEST_TIME
          ),
        ),
      }
    ),
    num_items=2,
    source=TestSource(),
  )

  rows = list(dataset.select_rows([PATH_WILDCARD]))
  assert rows == [
    {'text': 'abcd', 'double': 'abcd abcd', 'double.test_signal': {'firstchar': 'a', 'len': 9}},
    {'text': 'efghi', 'double': 'efghi efghi', 'double.test_signal': {'firstchar': 'e', 'len': 11}},
  ]

  # combine_columns=True.
  rows = list(dataset.select_rows([PATH_WILDCARD], combine_columns=True))
  assert rows == [
    {
      'text': 'abcd',
      'double': enriched_item('abcd abcd', {signal.key(): {'firstchar': 'a', 'len': 9}}),
    },
    {
      'text': 'efghi',
      'double': enriched_item('efghi efghi', {signal.key(): {'firstchar': 'e', 'len': 11}}),
    },
  ]


def test_map_non_root_output_errors(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data([{'text': 'abcd'}, {'text': 'efghi'}])

  def _map_fn(row: Item) -> Item:
    return row['text'] + ' ' + row['text']

  with pytest.raises(ValueError, match='Mapping to a nested path is not yet supported'):
    dataset.map(_map_fn, output_path=('double', 'notroot'), combine_columns=False)
