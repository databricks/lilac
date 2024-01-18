"""Tests for dataset.map()."""

import inspect
import re
import time
from typing import ClassVar, Iterable, Iterator, Optional
from unittest.mock import ANY

import pytest
from typing_extensions import override

from .. import tasks
from ..batch_utils import group_by_sorted_key_iter
from ..schema import (
  PATH_WILDCARD,
  VALUE_KEY,
  Field,
  Item,
  MapInfo,
  RichData,
  field,
  schema,
  span,
)
from ..signal import TextSignal, clear_signal_registry, register_signal
from ..source import clear_source_registry, register_source
from ..test_utils import (
  TEST_TIME,
  allow_any_datetime,
)
from .dataset import DatasetManifest, Filter, SelectGroupsResult, StatsResult
from .dataset_test_utils import (
  TEST_DATASET_NAME,
  TEST_NAMESPACE,
  TestDataMaker,
  TestProcessLogger,
  TestSource,
  enriched_item,
)

TEST_EXECUTION_TYPES = ['threads', 'processes']


class TestFirstCharSignal(TextSignal):
  name: ClassVar[str] = 'test_signal'

  @override
  def fields(self) -> Field:
    return field(fields={'len': 'int32', 'firstchar': 'string'})

  @override
  def compute(self, data: Iterable[RichData]) -> Iterator[Optional[Item]]:
    return ({'len': len(text_content), 'firstchar': text_content[0]} for text_content in data)


@pytest.fixture(scope='module', autouse=True)
def setup_teardown() -> Iterable[None]:
  allow_any_datetime(DatasetManifest)

  # Setup.
  clear_signal_registry()
  register_source(TestSource)
  register_signal(TestFirstCharSignal)

  # Unit test runs.
  yield
  # Teardown.
  clear_source_registry()
  clear_signal_registry()


@pytest.mark.parametrize('num_jobs', [-1, 1, 2])
@pytest.mark.parametrize('execution_type', TEST_EXECUTION_TYPES)
def test_map(
  num_jobs: int, execution_type: tasks.TaskExecutionType, make_test_data: TestDataMaker
) -> None:
  dataset = make_test_data([{'text': 'a sentence'}, {'text': 'b sentence'}])

  def _map_fn(item: Item) -> Item:
    return item['text'].upper()

  # Write the output to a new column.
  dataset.map(_map_fn, output_path='text_upper', num_jobs=num_jobs, execution_type=execution_type)

  assert dataset.manifest() == DatasetManifest(
    namespace=TEST_NAMESPACE,
    dataset_name=TEST_DATASET_NAME,
    data_schema=schema(
      {
        'text': 'string',
        'text_upper': field(
          dtype='string',
          map=MapInfo(
            fn_name='_map_fn',
            fn_source=inspect.getsource(_map_fn),
            date_created=TEST_TIME,
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
      'text_upper': 'A SENTENCE',
    },
    {
      'text': 'b sentence',
      'text_upper': 'B SENTENCE',
    },
  ]


@pytest.mark.parametrize('execution_type', TEST_EXECUTION_TYPES)
def test_map_idle_worker(
  execution_type: tasks.TaskExecutionType, make_test_data: TestDataMaker
) -> None:
  dataset = make_test_data(
    [
      {'text': 'a sentence'},
      {'text': 'b sentence'},
      {'text': 'c sentence'},
    ]
  )

  def _map_fn(item: Item) -> Item:
    return item['text'].upper()

  dataset.map(_map_fn, output_path='text_upper', num_jobs=4, execution_type=execution_type)
  rows = list(dataset.select_rows([PATH_WILDCARD]))
  assert len(rows) == 3


@pytest.mark.parametrize('num_jobs', [-1, 1, 2])
@pytest.mark.parametrize('execution_type', TEST_EXECUTION_TYPES)
def test_map_signal(
  num_jobs: int, execution_type: tasks.TaskExecutionType, make_test_data: TestDataMaker
) -> None:
  dataset = make_test_data([{'text': 'a sentence'}, {'text': 'b sentence'}])

  signal = TestFirstCharSignal()
  dataset.compute_signal(signal, 'text')

  def _map_fn(item: Item) -> Item:
    return {'result': f'{item["text"]["test_signal"]["firstchar"]}_{len(item["text"][VALUE_KEY])}'}

  # Write the output to a new column.
  dataset.map(_map_fn, output_path='output_text', num_jobs=num_jobs, execution_type=execution_type)

  assert dataset.manifest() == DatasetManifest(
    namespace=TEST_NAMESPACE,
    dataset_name=TEST_DATASET_NAME,
    data_schema=schema(
      {
        'text': field(
          'string',
          fields={'test_signal': field(fields={'len': 'int32', 'firstchar': 'string'}, signal=ANY)},
        ),
        'output_text': field(
          fields={'result': 'string'},
          map=MapInfo(
            fn_name='_map_fn',
            fn_source=inspect.getsource(_map_fn),
            date_created=TEST_TIME,
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
      'text.test_signal.firstchar': 'a',
      'text.test_signal.len': 10,
      'output_text.result': 'a_10',
    },
    {
      'text': 'b sentence',
      'text.test_signal.firstchar': 'b',
      'text.test_signal.len': 10,
      'output_text.result': 'b_10',
    },
  ]


@pytest.mark.parametrize('num_jobs', [-1, 1, 2])
@pytest.mark.parametrize('execution_type', TEST_EXECUTION_TYPES)
def test_map_input_path(
  num_jobs: int, execution_type: tasks.TaskExecutionType, make_test_data: TestDataMaker
) -> None:
  dataset = make_test_data(
    [
      {'id': 0, 'text': 'a'},
      {'id': 1, 'text': 'b'},
      {'id': 2, 'text': 'c'},
    ]
  )

  def _upper(row: Item) -> Item:
    return str(row).upper()

  # Write the output to a new column.
  dataset.map(
    _upper,
    input_path='text',
    output_path='text_upper',
    num_jobs=num_jobs,
    execution_type=execution_type,
  )

  # The schema should not reflect the output of the map as it didn't finish.
  assert dataset.manifest() == DatasetManifest(
    namespace=TEST_NAMESPACE,
    dataset_name=TEST_DATASET_NAME,
    data_schema=schema(
      {
        'text': 'string',
        'id': 'int32',
        'text_upper': field(
          dtype='string',
          map=MapInfo(
            fn_name='_upper',
            input_path=('text',),
            fn_source=inspect.getsource(_upper),
            date_created=TEST_TIME,
          ),
        ),
      }
    ),
    num_items=3,
    source=TestSource(),
  )
  # The rows should not reflect the output of the unfinished map.
  rows = list(dataset.select_rows([PATH_WILDCARD]))
  assert rows == [
    {'text': 'a', 'id': 0, 'text_upper': 'A'},
    {'text': 'b', 'id': 1, 'text_upper': 'B'},
    {'text': 'c', 'id': 2, 'text_upper': 'C'},
  ]


@pytest.mark.parametrize('num_jobs', [-1, 1, 2])
@pytest.mark.parametrize('execution_type', TEST_EXECUTION_TYPES)
def test_map_input_path_nested(
  num_jobs: int, execution_type: tasks.TaskExecutionType, make_test_data: TestDataMaker
) -> None:
  dataset = make_test_data(
    [
      {'id': 0, 'texts': [{'value': 'a'}]},
      {'id': 1, 'texts': [{'value': 'b'}, {'value': 'c'}]},
      {'id': 2, 'texts': [{'value': 'd'}, {'value': 'e'}, {'value': 'f'}]},
    ]
  )

  def _upper(row: Item) -> Item:
    return str(row).upper()

  dataset.map(
    _upper,
    input_path=('texts', PATH_WILDCARD, 'value'),
    output_path='texts_upper',
    num_jobs=num_jobs,
    execution_type=execution_type,
  )

  # The schema should not reflect the output of the map as it didn't finish.
  assert dataset.manifest() == DatasetManifest(
    namespace=TEST_NAMESPACE,
    dataset_name=TEST_DATASET_NAME,
    data_schema=schema(
      {
        'texts': [{'value': 'string'}],
        'id': 'int32',
        'texts_upper': field(
          fields=['string'],
          map=MapInfo(
            fn_name='_upper',
            input_path=('texts', PATH_WILDCARD, 'value'),
            fn_source=inspect.getsource(_upper),
            date_created=TEST_TIME,
          ),
        ),
      }
    ),
    num_items=3,
    source=TestSource(),
  )
  # The rows should not reflect the output of the unfinished map.
  rows = list(dataset.select_rows([PATH_WILDCARD]))
  assert rows == [
    {'id': 0, 'texts.*.value': ['a'], 'texts_upper': ['A']},
    {'id': 1, 'texts.*.value': ['b', 'c'], 'texts_upper': ['B', 'C']},
    {'id': 2, 'texts.*.value': ['d', 'e', 'f'], 'texts_upper': ['D', 'E', 'F']},
  ]


@pytest.mark.parametrize('num_jobs', [-1, 1, 2])
@pytest.mark.parametrize('execution_type', TEST_EXECUTION_TYPES)
def test_map_continuation(
  num_jobs: int,
  execution_type: tasks.TaskExecutionType,
  make_test_data: TestDataMaker,
  test_process_logger: TestProcessLogger,
) -> None:
  # Some flakiness in this test.
  # Say you have 2 workers. Worker 1 gets id 0. Worker 2 gets id 1, 2, 3, 4, 5....
  # For whatever reason worker 2 gets all the cpu time and gets to item N, which throws.
  # The pool is accumulating finished values from worker 2, while waiting on worker 1 because it has
  # in-order guarantees. But when worker 2 throws the exception, the whole job fails, without a
  # single item having been returned.
  # Threads seem to be the flakiest, even with very large num_items, because the GIL is
  # conservative about switching threads. The time.sleep() seems to give the GIL a hint to switch.
  num_items = 1000
  dataset = make_test_data([{'id': i} for i in range(num_items)])

  def _map_fn(item: Item, first_run: bool) -> Item:
    time.sleep(0.0001)
    if first_run and item['id'] == num_items - 1:
      raise ValueError('Throwing')

    return item['id']

  def _map_fn_1(item: Item) -> Item:
    return _map_fn(item, first_run=True)

  def _map_fn_2(item: Item) -> Item:
    test_process_logger.log_event(item['id'])
    return _map_fn(item, first_run=False)

  # Write the output to a new column.
  with pytest.raises(Exception):
    dataset.map(_map_fn_1, output_path='map_id', num_jobs=num_jobs, execution_type=execution_type)

  # The schema should not reflect the output of the map as it didn't finish.
  assert dataset.manifest() == DatasetManifest(
    namespace=TEST_NAMESPACE,
    dataset_name=TEST_DATASET_NAME,
    data_schema=schema({'id': 'int32'}),
    num_items=num_items,
    source=TestSource(),
  )
  # The rows should not reflect the output of the unfinished map.
  rows = list(dataset.select_rows([PATH_WILDCARD]))
  assert rows == [{'id': i} for i in range(num_items)]

  # Hardcode this to thread-type, because the test_process_logger takes 2 seconds to serialize.
  # We're only really testing whether the continuation is reusing the saved results, anyway.
  dataset.map(_map_fn_2, output_path='map_id', num_jobs=1, execution_type='threads')

  assert 0 not in test_process_logger.get_logs()

  assert dataset.manifest() == DatasetManifest(
    namespace=TEST_NAMESPACE,
    dataset_name=TEST_DATASET_NAME,
    data_schema=schema(
      {
        'id': 'int32',
        'map_id': field(
          dtype='int64',
          map=MapInfo(
            fn_name='_map_fn_2', fn_source=inspect.getsource(_map_fn_2), date_created=TEST_TIME
          ),
        ),
      }
    ),
    num_items=num_items,
    source=TestSource(),
  )

  rows = list(dataset.select_rows([PATH_WILDCARD]))
  assert sorted(rows, key=lambda obj: obj['id']) == [
    {'id': i, 'map_id': i} for i in range(num_items)
  ]


@pytest.mark.parametrize('num_jobs', [-1, 1, 2])
@pytest.mark.parametrize('execution_type', TEST_EXECUTION_TYPES)
def test_map_continuation_overwrite(
  num_jobs: int,
  execution_type: tasks.TaskExecutionType,
  make_test_data: TestDataMaker,
  test_process_logger: TestProcessLogger,
) -> None:
  dataset = make_test_data(
    [
      {'id': 0, 'text': 'a sentence'},
      {'id': 1, 'text': 'b sentence'},
      {'id': 2, 'text': 'c sentence'},
    ]
  )

  def _map_fn(item: Item, first_run: bool) -> Item:
    test_process_logger.log_event(item['id'])

    if first_run and item['id'] == 1:
      raise ValueError('Throwing')

    return item['id']

  def _map_fn_1(item: Item) -> Item:
    return _map_fn(item, first_run=True)

  def _map_fn_2(item: Item) -> Item:
    return _map_fn(item, first_run=False)

  # Write the output to a new column.
  with pytest.raises(Exception):
    dataset.map(_map_fn_1, output_path='map_id', num_jobs=num_jobs, execution_type=execution_type)

  test_process_logger.clear_logs()

  dataset.map(
    _map_fn_2,
    output_path='map_id',
    overwrite=True,
    num_jobs=num_jobs,
    execution_type=execution_type,
  )

  # Map should be called for all ids.
  assert set(sorted(test_process_logger.get_logs())) == set([0, 1, 2])

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
            fn_name='_map_fn_2', fn_source=inspect.getsource(_map_fn_2), date_created=TEST_TIME
          ),
        ),
      }
    ),
    num_items=3,
    source=TestSource(),
  )

  rows = list(dataset.select_rows([PATH_WILDCARD]))
  assert rows == [
    {'text': 'a sentence', 'id': 0, 'map_id': 0},
    {'text': 'b sentence', 'id': 1, 'map_id': 1},
    {'text': 'c sentence', 'id': 2, 'map_id': 2},
  ]


@pytest.mark.parametrize('num_jobs', [-1, 1, 2])
@pytest.mark.parametrize('execution_type', TEST_EXECUTION_TYPES)
def test_map_limit(
  num_jobs: int, execution_type: tasks.TaskExecutionType, make_test_data: TestDataMaker
) -> None:
  dataset = make_test_data([{'text': letter} for letter in 'abcdefghijklmnopqrstuvwxyz'])

  def _map_fn(item: Item) -> Item:
    return item['text'].upper()

  # Write the output to a new column.
  dataset.map(
    _map_fn, output_path='text_upper', num_jobs=num_jobs, execution_type=execution_type, limit=10
  )

  rows = list(
    dataset.select_rows([PATH_WILDCARD], filters=[Filter(path=('text_upper',), op='exists')])
  )
  assert len(rows) == 10


@pytest.mark.parametrize('num_jobs', [-1, 1, 2])
@pytest.mark.parametrize('execution_type', TEST_EXECUTION_TYPES)
def test_map_filter(
  num_jobs: int, execution_type: tasks.TaskExecutionType, make_test_data: TestDataMaker
) -> None:
  dataset = make_test_data([{'text': letter} for letter in 'abcdefghijklmnopqrstuvwxyz'])

  def _map_fn(item: Item) -> Item:
    return item['text'].upper()

  # Write the output to a new column.
  dataset.map(
    _map_fn,
    output_path='text_upper',
    num_jobs=num_jobs,
    execution_type=execution_type,
    filters=[Filter(path=('text',), op='in', value=['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i'])],
  )

  rows = list(
    dataset.select_rows([PATH_WILDCARD], filters=[Filter(path=('text_upper',), op='exists')])
  )
  assert len(rows) == 9


@pytest.mark.parametrize('num_jobs', [-1, 1, 2])
@pytest.mark.parametrize('execution_type', TEST_EXECUTION_TYPES)
@pytest.mark.parametrize('batch_size', [-1, 2, 3])
def test_map_batch(
  num_jobs: int,
  execution_type: tasks.TaskExecutionType,
  batch_size: Optional[int],
  make_test_data: TestDataMaker,
) -> None:
  dataset = make_test_data([{'text': letter} for letter in 'abcd'])

  def _map_fn(items: list[Item]) -> list[Item]:
    return [item['text'].upper() for item in items]

  # Write the output to a new column.
  dataset.map(
    _map_fn,
    output_path='text_upper',
    batch_size=batch_size,
    num_jobs=num_jobs,
    execution_type=execution_type,
  )

  rows = list(
    dataset.select_rows([PATH_WILDCARD], filters=[Filter(path=('text_upper',), op='exists')])
  )
  assert rows == [
    {
      'text': 'a',
      'text_upper': 'A',
    },
    {
      'text': 'b',
      'text_upper': 'B',
    },
    {
      'text': 'c',
      'text_upper': 'C',
    },
    {
      'text': 'd',
      'text_upper': 'D',
    },
  ]


@pytest.mark.parametrize('num_jobs', [-1, 1, 2])
@pytest.mark.parametrize('execution_type', TEST_EXECUTION_TYPES)
def test_map_deleted_interaction(
  num_jobs: int, execution_type: tasks.TaskExecutionType, make_test_data: TestDataMaker
) -> None:
  dataset = make_test_data([{'text': letter} for letter in 'abcde'])

  def _map_fn(item: Item) -> Item:
    return item['text'].upper()

  dataset.delete_rows(row_ids=['00001', '00002', '00003'])

  dataset.map(_map_fn, output_path='text_upper', num_jobs=num_jobs, execution_type=execution_type)

  rows = list(dataset.select_rows(['text_upper'], include_deleted=True))
  assert rows == [
    {'text_upper': None},
    {'text_upper': None},
    {'text_upper': None},
    {'text_upper': 'D'},
    {'text_upper': 'E'},
  ]

  dataset.map(
    _map_fn,
    output_path='text_upper',
    num_jobs=num_jobs,
    execution_type=execution_type,
    overwrite=True,
    include_deleted=True,
  )

  rows = list(dataset.select_rows(['text_upper'], include_deleted=True))
  assert rows == [
    {'text_upper': 'A'},
    {'text_upper': 'B'},
    {'text_upper': 'C'},
    {'text_upper': 'D'},
    {'text_upper': 'E'},
  ]


@pytest.mark.parametrize('num_jobs', [-1, 1, 2])
@pytest.mark.parametrize('execution_type', TEST_EXECUTION_TYPES)
def test_map_overwrite(
  num_jobs: int, execution_type: tasks.TaskExecutionType, make_test_data: TestDataMaker
) -> None:
  dataset = make_test_data([{'text': 'a'}, {'text': 'b'}])

  prefix = '0'

  def _map_fn(item: Item) -> Item:
    nonlocal prefix
    return prefix + item['text']

  # Write the output to a new column.
  dataset.map(_map_fn, output_path='map_text', num_jobs=num_jobs, execution_type=execution_type)

  rows = list(dataset.select_rows([PATH_WILDCARD]))
  assert rows == [{'text': 'a', 'map_text': '0a'}, {'text': 'b', 'map_text': '0b'}]

  with pytest.raises(ValueError, match=' which already exists in the dataset'):
    dataset.map(_map_fn, output_path='map_text', execution_type=execution_type)

  prefix = '1'
  # Overwrite the output
  dataset.map(_map_fn, output_path='map_text', overwrite=True, execution_type=execution_type)

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


def test_map_overwrite_where_input_is_output(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data([{'text': 'a'}, {'text': 'b'}])

  def prefix_text(text: str) -> str:
    return '_' + text

  dataset.map(prefix_text, input_path='text', output_path='prefixed_text', overwrite=True)
  rows = list(dataset.select_rows(['prefixed_text']))
  assert rows == [{'prefixed_text': '_a'}, {'prefixed_text': '_b'}]

  # Overwrite prefixed_text by adding another prefix.
  dataset.map(prefix_text, input_path='prefixed_text', output_path='prefixed_text', overwrite=True)
  rows = list(dataset.select_rows(['prefixed_text']))
  assert rows == [{'prefixed_text': '__a'}, {'prefixed_text': '__b'}]

  def prefix_text_in_row(row: Item) -> str:
    return '_' + row['prefixed_text']

  # Overwrite prefixed_text by adding yet another prefix, this time iterating over the entire row.
  dataset.map(prefix_text_in_row, output_path='prefixed_text', overwrite=True)
  rows = list(dataset.select_rows(['prefixed_text']))
  assert rows == [{'prefixed_text': '___a'}, {'prefixed_text': '___b'}]

  assert dataset.manifest() == DatasetManifest(
    namespace=TEST_NAMESPACE,
    dataset_name=TEST_DATASET_NAME,
    data_schema=schema(
      {
        'text': 'string',
        'prefixed_text': field(
          dtype='string',
          map=MapInfo(
            fn_name='prefix_text_in_row',
            fn_source=inspect.getsource(prefix_text_in_row),
            date_created=TEST_TIME,
          ),
        ),
      }
    ),
    num_items=2,
    source=TestSource(),
  )


@pytest.mark.parametrize('num_jobs', [-1, 1, 2])
@pytest.mark.parametrize('execution_type', TEST_EXECUTION_TYPES)
def test_map_output_path_returns_iterable(
  num_jobs: int, execution_type: tasks.TaskExecutionType, make_test_data: TestDataMaker
) -> None:
  dataset = make_test_data([{'text': 'a sentence'}, {'text': 'b sentence'}])

  def _map_fn(item: Item) -> Item:
    return item['text'].upper()

  # Write the output to a new column.
  result_rows = dataset.map(
    _map_fn, output_path='text_upper', num_jobs=num_jobs, execution_type=execution_type
  )

  assert list(result_rows) == [
    'A SENTENCE',
    'B SENTENCE',
  ]

  rows = list(dataset.select_rows([PATH_WILDCARD]))
  assert rows == [
    {
      'text': 'a sentence',
      'text_upper': 'A SENTENCE',
    },
    {
      'text': 'b sentence',
      'text_upper': 'B SENTENCE',
    },
  ]


@pytest.mark.parametrize('num_jobs', [-1, 1, 2])
@pytest.mark.parametrize('execution_type', TEST_EXECUTION_TYPES)
def test_map_no_output_col(
  num_jobs: int, execution_type: tasks.TaskExecutionType, make_test_data: TestDataMaker
) -> None:
  dataset = make_test_data([{'text': 'a sentence'}, {'text': 'b sentence'}])

  def _map_fn(item: Item) -> Item:
    return item['text'].upper()

  map_output = dataset.map(_map_fn, num_jobs=num_jobs, execution_type=execution_type)

  assert list(map_output) == [
    'A SENTENCE',
    'B SENTENCE',
  ]
  # Make sure we can iterate again.
  assert list(map_output) == [
    'A SENTENCE',
    'B SENTENCE',
  ]

  # The manifest should contain no new columns.
  assert dataset.manifest() == DatasetManifest(
    namespace=TEST_NAMESPACE,
    dataset_name=TEST_DATASET_NAME,
    data_schema=schema({'text': field('string')}),
    num_items=2,
    source=TestSource(),
  )

  # The new columns should not be saved anywhere.
  rows = list(dataset.select_rows([PATH_WILDCARD]))
  assert rows == [{'text': 'a sentence'}, {'text': 'b sentence'}]


def test_map_chained(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data([{'text': 'a sentence'}, {'text': 'b sentence'}])

  def _split_fn(item: Item) -> Item:
    return item['text'].split(' ')

  dataset.map(_split_fn, output_path='splits')

  def _rearrange_fn(item: Item) -> Item:
    return item['splits'][1] + ' ' + item['splits'][0]

  dataset.map(_rearrange_fn, output_path='rearrange')

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


def test_map_over_enriched_item(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data([{'text': 'a sentence'}, {'text': 'b sentence'}])

  signal = TestFirstCharSignal()
  dataset.compute_signal(signal, 'text')

  def _map_fn(item: Item) -> Item:
    return {'result': f'{item["text"]["test_signal"]["firstchar"]}_{len(item["text"][VALUE_KEY])}'}

  # Write the output to a new column.
  dataset.map(_map_fn, output_path='output_text')

  assert dataset.manifest() == DatasetManifest(
    namespace=TEST_NAMESPACE,
    dataset_name=TEST_DATASET_NAME,
    data_schema=schema(
      {
        'text': field(
          'string',
          fields={'test_signal': field(fields={'len': 'int32', 'firstchar': 'string'}, signal=ANY)},
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
      'text.test_signal.firstchar': 'a',
      'text.test_signal.len': 10,
      'output_text.result': 'a_10',
    },
    {
      'text': 'b sentence',
      'text.test_signal.firstchar': 'b',
      'text.test_signal.len': 10,
      'output_text.result': 'b_10',
    },
  ]


def test_map_on_double_nested_input(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data(
    [
      {'texts': [['a', 'b'], ['c'], ['dd', 'e']]},
      {'texts': [['ff', 'ggg']]},
    ]
  )

  dataset.map(lambda x: len(x), 'texts', output_path='texts_len')
  dataset.map(lambda x: len(x), 'texts.*', output_path='texts[i]_len')
  dataset.map(lambda x: len(x), 'texts.*.*', output_path='texts[i][j]_len')

  rows = list(dataset.select_rows())
  assert rows == [
    {
      'texts': [['a', 'b'], ['c'], ['dd', 'e']],
      'texts_len': 3,
      'texts[i]_len': [2, 1, 2],
      'texts[i][j]_len': [[1, 1], [1], [2, 1]],
    },
    {
      'texts': [['ff', 'ggg']],
      'texts_len': 1,
      'texts[i]_len': [2],
      'texts[i][j]_len': [[2, 3]],
    },
  ]


def test_map_select_subfields_of_repeated_dicts(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data(
    [
      {
        'people': [
          {'name': 'A', 'phones': [1, 2, 3], 'address': 'a'},
          {'name': 'BB', 'phones': [4], 'address': 'b'},
          {'name': 'C', 'phones': [5], 'address': 'c'},
        ]
      },
      {
        'people': [
          {'name': 'D', 'phones': [6], 'address': 'd'},
          {'name': 'EEE', 'phones': [7, 8], 'address': 'e'},
        ]
      },
    ]
  )

  dataset.map(lambda x: len(x), 'people', output_path='people_len')
  dataset.map(lambda x: x['name'], 'people.*', output_path='person_name')
  dataset.map(lambda x: len(x), 'people.*.name', output_path='len_name')
  dataset.map(lambda x: len(x), 'people.*.phones', output_path='len_phones')
  dataset.map(lambda x: x - 1, 'people.*.phones.*', output_path='phones_minus_one')

  # No input path.
  dataset.map(lambda x: 'people' in x and 'name' in x['people'][0], output_path='has_name')

  rows = list(
    dataset.select_rows(
      ['people_len', 'person_name', 'len_name', 'len_phones', 'phones_minus_one', 'has_name']
    )
  )
  assert rows == [
    {
      'people_len': 3,
      'person_name': ['A', 'BB', 'C'],
      'len_name': [1, 2, 1],
      'len_phones': [3, 1, 1],
      'phones_minus_one': [[0, 1, 2], [3], [4]],
      'has_name': True,
    },
    {
      'people_len': 2,
      'person_name': ['D', 'EEE'],
      'len_name': [1, 3],
      'len_phones': [1, 2],
      'phones_minus_one': [[5], [6, 7]],
      'has_name': True,
    },
  ]


def test_map_nests_under_repeated(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data(
    [
      {'people': [{'name': 'A'}, {'name': 'BB'}, {'name': 'C'}]},
      {'people': [{'name': 'D'}, {'name': 'EEE'}]},
    ]
  )

  dataset.map(lambda x: len(x), 'people.*.name', output_path='people.*.len_name')

  rows = list(dataset.select_rows(combine_columns=True))
  assert rows == [
    {
      'people': [
        {'name': 'A', 'len_name': 1},
        {'name': 'BB', 'len_name': 2},
        {'name': 'C', 'len_name': 1},
      ]
    },
    {'people': [{'name': 'D', 'len_name': 1}, {'name': 'EEE', 'len_name': 3}]},
  ]

  rows = list(dataset.select_rows())
  assert rows == [
    {'people.*.name': ['A', 'BB', 'C'], 'people.*.len_name': [1, 2, 1]},
    {'people.*.name': ['D', 'EEE'], 'people.*.len_name': [1, 3]},
  ]


def test_map_nests_under_field_of_repeated(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data(
    [
      {'people': [{'name': 'A', 'info': {'extra': 1}}, {'name': 'BB'}, {'name': 'C'}]},
      {'people': [{'name': 'D'}, {'name': 'EEE'}]},
    ]
  )

  dataset.map(lambda x: len(x), 'people.*.name', output_path='people.*.info.len_name')

  rows = list(dataset.select_rows(combine_columns=True))
  assert rows == [
    {
      'people': [
        {'name': 'A', 'info': {'extra': 1, 'len_name': 1}},
        {'name': 'BB', 'info': {'len_name': 2}},
        {'name': 'C', 'info': {'len_name': 1}},
      ]
    },
    {
      'people': [
        {'name': 'D', 'info': {'len_name': 1}},
        {'name': 'EEE', 'info': {'len_name': 3}},
      ]
    },
  ]


def test_map_nests_under_a_parent_of_input_path(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data(
    [
      {
        'people': [
          {'name': 'A', 'address': {'zip': 1}},
          {'name': 'B'},
          {'name': 'C', 'address': {'zip': 2}},
        ]
      },
      {
        'people': [
          {'name': 'D', 'address': {'zip': 3}},
          {'name': 'E', 'address': {}},
        ]
      },
    ]
  )

  def zip_code_verifier(zip_code: int) -> bool:
    return zip_code != 2

  dataset.map(zip_code_verifier, 'people.*.address.zip', output_path='people.*.verified')

  rows = list(dataset.select_rows(combine_columns=True))
  assert rows == [
    {
      'people': [
        {'name': 'A', 'address': {'zip': 1}, 'verified': True},
        {'name': 'B', 'address': None, 'verified': None},
        {'name': 'C', 'address': {'zip': 2}, 'verified': False},
      ]
    },
    {
      'people': [
        {'name': 'D', 'address': {'zip': 3}, 'verified': True},
        {'name': 'E', 'address': {'zip': None}, 'verified': None},
      ]
    },
  ]


def test_transform_with_sort_by(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data(
    [
      {'text': 'a', 'cluster_id': 2},
      {'text': 'b', 'cluster_id': 1},
      {'text': 'c', 'cluster_id': 1},
      {'text': 'd', 'cluster_id': 2},
      {'text': 'e', 'cluster_id': 2},
      {'text': 'f', 'cluster_id': 3},
    ]
  )

  def aggregate_cluster(items: Iterator[str]) -> Iterator[Item]:
    groups = group_by_sorted_key_iter(items, lambda x: x)
    for group in groups:
      for _ in group:
        yield len(group)

  dataset.transform(
    aggregate_cluster, input_path='cluster_id', output_path='cluster_size', sort_by='cluster_id'
  )

  rows = list(dataset.select_rows())
  assert rows == [
    {'text': 'a', 'cluster_id': 2, 'cluster_size': 3},
    {'text': 'b', 'cluster_id': 1, 'cluster_size': 2},
    {'text': 'c', 'cluster_id': 1, 'cluster_size': 2},
    {'text': 'd', 'cluster_id': 2, 'cluster_size': 3},
    {'text': 'e', 'cluster_id': 2, 'cluster_size': 3},
    {'text': 'f', 'cluster_id': 3, 'cluster_size': 1},
  ]


def test_signal_on_map_output(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data([{'text': 'abcd'}, {'text': 'efghi'}])

  def _map_fn(item: Item) -> Item:
    return item['text'] + ' ' + item['text']

  dataset.map(_map_fn, output_path='double')

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
          fields={'test_signal': field(fields={'len': 'int32', 'firstchar': 'string'}, signal=ANY)},
          map=MapInfo(
            fn_name='_map_fn', fn_source=inspect.getsource(_map_fn), date_created=TEST_TIME
          ),
        ),
      }
    ),
    num_items=2,
    source=TestSource(),
  )

  assert list(dataset.select_rows([PATH_WILDCARD])) == [
    {
      'text': 'abcd',
      'double': 'abcd abcd',
      'double.test_signal.firstchar': 'a',
      'double.test_signal.len': 9,
    },
    {
      'text': 'efghi',
      'double': 'efghi efghi',
      'double.test_signal.firstchar': 'e',
      'double.test_signal.len': 11,
    },
  ]

  # Select a struct root.
  assert list(dataset.select_rows([('double', 'test_signal')])) == [
    {
      'double.test_signal': {'firstchar': 'a', 'len': 9},
    },
    {
      'double.test_signal': {'firstchar': 'e', 'len': 11},
    },
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


def test_map_nested_output_path(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data([{'parent': {'text': 'a'}}, {'parent': {'text': 'abc'}}])

  def _map_fn(item: Item) -> Item:
    return {'value': len(item['parent']['text'])}

  dataset.map(_map_fn, output_path='parent.text.len')

  assert dataset.manifest() == DatasetManifest(
    namespace=TEST_NAMESPACE,
    dataset_name=TEST_DATASET_NAME,
    data_schema=schema(
      {
        'parent': field(
          fields={
            'text': field(
              'string',
              fields={
                'len': field(
                  fields={'value': 'int64'},
                  map=MapInfo(
                    fn_name='_map_fn',
                    fn_source=inspect.getsource(_map_fn),
                    date_created=TEST_TIME,
                  ),
                )
              },
            )
          }
        ),
      }
    ),
    num_items=2,
    source=TestSource(),
  )

  rows = list(dataset.select_rows([PATH_WILDCARD], combine_columns=True))
  assert rows == [
    {
      'parent': {'text': enriched_item('a', {'len': {'value': 1}})},
    },
    {
      'parent': {'text': enriched_item('abc', {'len': {'value': 3}})},
    },
  ]


def test_map_span(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data([{'text': 'ab'}, {'text': 'bc'}])

  # Return coordinates of 'b'.
  def _map_fn(item: Item) -> Item:
    return [
      span(m.start(), m.end(), {'len': m.end() - m.start()}) for m in re.finditer('b', item['text'])
    ]

  dataset.map(_map_fn, output_path='text.b_span')

  assert dataset.manifest() == DatasetManifest(
    namespace=TEST_NAMESPACE,
    dataset_name=TEST_DATASET_NAME,
    data_schema=schema(
      {
        'text': field(
          'string',
          fields={
            'b_span': field(
              fields=[field(dtype='string_span', fields={'len': 'int64'})],
              map=MapInfo(
                fn_name='_map_fn',
                fn_source=inspect.getsource(_map_fn),
                date_created=TEST_TIME,
              ),
            )
          },
        )
      }
    ),
    num_items=2,
    source=TestSource(),
  )

  rows = list(dataset.select_rows([PATH_WILDCARD], combine_columns=True))
  assert rows == [
    {
      'text': enriched_item('ab', {'b_span': [span(1, 2, {'len': 1})]}),
    },
    {
      'text': enriched_item('bc', {'b_span': [span(0, 1, {'len': 1})]}),
    },
  ]


def test_map_ergonomics(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data([{'text': 'a sentence'}, {'text': 'b sentence'}])

  def _fn_kw(item: Item) -> Item:
    return item['text'] + ' map'

  def _fn(x: Item) -> Item:
    return x['text'] + ' map'

  # Write the output to a new column.
  dataset.map(_fn_kw, output_path='_fn_kw')
  dataset.map(_fn, output_path='_fn')

  assert dataset.manifest() == DatasetManifest(
    namespace=TEST_NAMESPACE,
    dataset_name=TEST_DATASET_NAME,
    data_schema=schema(
      {
        'text': 'string',
        '_fn_kw': field(
          dtype='string',
          map=MapInfo(
            fn_name='_fn_kw', fn_source=inspect.getsource(_fn_kw), date_created=TEST_TIME
          ),
        ),
        '_fn': field(
          dtype='string',
          map=MapInfo(fn_name='_fn', fn_source=inspect.getsource(_fn), date_created=TEST_TIME),
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
      '_fn_kw': 'a sentence map',
      '_fn': 'a sentence map',
    },
    {
      'text': 'b sentence',
      '_fn_kw': 'b sentence map',
      '_fn': 'b sentence map',
    },
  ]


def test_map_ergonomics_invalid_args(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data([{'text': 'a sentence'}, {'text': 'b sentence'}])

  def _map_noargs() -> None:
    pass

  with pytest.raises(TypeError, match=re.escape('takes 0 positional arguments but 1 was given')):
    dataset.map(_map_noargs, output_path='_map_noargs')

  def _map_toomany_args(row: Item, job_id: int, extra_arg: int) -> None:
    pass

  with pytest.raises(TypeError, match=re.escape('missing 2 required positional arguments')):
    dataset.map(_map_toomany_args, output_path='_map_toomany_args')


def test_map_nested_output_another_cardinality_fails(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data(
    [{'text': 'abcd', 'parent': ['a', 'b']}, {'text': 'efghi', 'parent': ['c', 'd']}]
  )

  def _map_fn(item: Item) -> Item:
    res = item['text'] + ' ' + item['text']
    return res

  with pytest.raises(
    AssertionError,
    match=re.escape(
      "`input_path` None and `output_path` ('parent', '*', 'output') have different cardinalities"
    ),
  ):
    dataset.map(_map_fn, output_path='parent.*.output')


def test_map_with_span_resolving(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data([{'text': 'abcd'}, {'text': 'efghi'}])

  def skip_first_and_last_letter(item: str) -> Item:
    return span(1, len(item) - 1)

  dataset.map(skip_first_and_last_letter, input_path='text', output_path='skip')

  result = dataset.select_groups('skip')
  assert result == SelectGroupsResult(too_many_distinct=False, counts=[('bc', 1), ('fgh', 1)])

  stats = dataset.stats('skip')
  assert stats == StatsResult(
    path=('skip',), total_count=2, approx_count_distinct=2, avg_text_length=2.0
  )

  rows = dataset.select_rows()
  assert list(rows) == [
    {'text': 'abcd', 'skip': span(1, 3)},
    {'text': 'efghi', 'skip': span(1, 4)},
  ]


def test_transform(make_test_data: TestDataMaker) -> None:
  def text_len(items: Iterator[Item]) -> Iterator[Item]:
    for item in items:
      yield len(item['text'])

  dataset = make_test_data([{'text': 'abcd'}, {'text': 'efghi'}])
  dataset.transform(text_len, output_path='text_len')

  rows = dataset.select_rows()
  assert list(rows) == [{'text': 'abcd', 'text_len': 4}, {'text': 'efghi', 'text_len': 5}]


def test_transform_with_input_path(make_test_data: TestDataMaker) -> None:
  def text_len(texts: Iterator[Item]) -> Iterator[Item]:
    for text in texts:
      yield len(text)

  dataset = make_test_data([{'text': 'abcd'}, {'text': 'efghi'}])
  dataset.transform(text_len, input_path='text', output_path='text_len')

  rows = dataset.select_rows()
  assert list(rows) == [{'text': 'abcd', 'text_len': 4}, {'text': 'efghi', 'text_len': 5}]


def test_transform_size_mismatch(make_test_data: TestDataMaker) -> None:
  def text_len(texts: Iterator[Item]) -> Iterator[Item]:
    for i, text in enumerate(texts):
      # Skip the first item.
      if i > 0:
        yield len(text)

  dataset = make_test_data([{'text': 'abcd'}, {'text': 'efghi'}])
  with pytest.raises(Exception):
    dataset.transform(text_len, input_path='text', output_path='text_len')


def test_map_outputs_long_string_that_promotes_to_media(make_test_data: TestDataMaker) -> None:
  def long_str(text: str) -> str:
    return text * 100

  dataset = make_test_data([{'text': 'abcd'}, {'text': 'efghi'}])
  dataset.map(long_str, input_path='text', output_path='text_long')

  assert ('text_long',) in dataset.settings().ui.media_paths
