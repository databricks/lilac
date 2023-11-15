"""Tests for dataset.map()."""

import inspect
from typing import ClassVar, Iterable, Literal, Optional

import pytest
from distributed import Client, LocalCluster
from typing_extensions import override

from .. import tasks
from ..schema import PATH_WILDCARD, VALUE_KEY, Field, Item, MapInfo, RichData, field, schema
from ..signal import TextSignal, clear_signal_registry, register_signal
from ..source import clear_source_registry, register_source
from ..test_utils import (
  TEST_TIME,
  allow_any_datetime,
)
from .dataset import DatasetManifest
from .dataset_test_utils import (
  TEST_DATASET_NAME,
  TEST_NAMESPACE,
  TestDaskLogger,
  TestDataMaker,
  TestSource,
  enriched_item,
)


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
  dask_cluster = LocalCluster(n_workers=2, threads_per_worker=2, processes=False)
  dask_client = Client(dask_cluster)
  tasks._TASK_MANAGER = tasks.TaskManager(dask_client=dask_client)

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

  dask_client.shutdown()


@pytest.mark.parametrize('num_jobs', [-1, 1, 2])
def test_map(num_jobs: Literal[-1, 1, 2], make_test_data: TestDataMaker) -> None:
  dataset = make_test_data([{'text': 'a sentence'}, {'text': 'b sentence'}])

  signal = TestFirstCharSignal()
  dataset.compute_signal(signal, 'text')

  def _map_fn(row: Item, job_id: int) -> Item:
    return {'result': f'{row["text.test_signal"]["firstchar"]}_{len(row["text"])}'}

  # Write the output to a new column.
  dataset.map(_map_fn, output_path='output_text', combine_columns=False, num_jobs=num_jobs)

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
      'text.test_signal': {'firstchar': 'a', 'len': 10},
      'output_text': {'result': 'a_10'},
    },
    {
      'text': 'b sentence',
      'text.test_signal': {'firstchar': 'b', 'len': 10},
      'output_text': {'result': 'b_10'},
    },
  ]


def test_map_job_id(make_test_data: TestDataMaker, test_dask_logger: TestDaskLogger) -> None:
  dataset = make_test_data(
    [
      {'text': 'a sentence'},
      {'text': 'b sentence'},
      {'text': 'c sentence'},
      {'text': 'd sentence'},
      {'text': 'e sentence'},
    ]
  )

  def _map_fn(row: Item, job_id: int) -> Item:
    test_dask_logger.log_event(job_id)
    return {}

  dataset.map(_map_fn, output_path='map_id', combine_columns=False, num_jobs=3)

  assert set(test_dask_logger.get_logs()) == set([0, 1, 2])


@pytest.mark.parametrize('num_jobs', [1, 2])
def test_map_continuation(
  num_jobs: Literal[-1, 1, 2], make_test_data: TestDataMaker, test_dask_logger: TestDaskLogger
) -> None:
  dataset = make_test_data(
    [
      {'id': 0, 'text': 'a sentence'},
      {'id': 1, 'text': 'b sentence'},
      {'id': 2, 'text': 'c sentence'},
    ]
  )

  def _map_fn(row: Item, first_run: bool) -> Item:
    test_dask_logger.log_event(row['id'])

    if first_run and row['id'] == 1:
      raise ValueError('Throwing')

    return row['id']

  def _map_fn_1(row: Item, job_id: int) -> Item:
    return _map_fn(row, first_run=True)

  def _map_fn_2(row: Item, job_id: int) -> Item:
    return _map_fn(row, first_run=False)

  # Write the output to a new column.
  with pytest.raises(Exception):
    dataset.map(_map_fn_1, output_path='map_id', combine_columns=False, num_jobs=num_jobs)

  # The schema should not reflect the output of the map as it didn't finish.
  assert dataset.manifest() == DatasetManifest(
    namespace=TEST_NAMESPACE,
    dataset_name=TEST_DATASET_NAME,
    data_schema=schema({'text': 'string', 'id': 'int32'}),
    num_items=3,
    source=TestSource(),
  )
  # The rows should not reflect the output of the unfinished map.
  rows = list(dataset.select_rows([PATH_WILDCARD]))
  assert rows == [
    {'text': 'a sentence', 'id': 0},
    {'text': 'b sentence', 'id': 1},
    {'text': 'c sentence', 'id': 2},
  ]

  test_dask_logger.clear_logs()

  dataset.map(_map_fn_2, output_path='map_id', combine_columns=False, num_jobs=num_jobs)

  # The row_id=1 should be called for the continuation.
  assert 1 in test_dask_logger.get_logs()

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
def test_map_continuation_overwrite(
  num_jobs: Literal[-1, 1, 2], make_test_data: TestDataMaker, test_dask_logger: TestDaskLogger
) -> None:
  dataset = make_test_data(
    [
      {'id': 0, 'text': 'a sentence'},
      {'id': 1, 'text': 'b sentence'},
      {'id': 2, 'text': 'c sentence'},
    ]
  )

  def _map_fn(row: Item, first_run: bool) -> Item:
    test_dask_logger.log_event(row['id'])

    if first_run and row['id'] == 1:
      raise ValueError('Throwing')

    return row['id']

  def _map_fn_1(row: Item, job_id: int) -> Item:
    return _map_fn(row, first_run=True)

  def _map_fn_2(row: Item, job_id: int) -> Item:
    return _map_fn(row, first_run=False)

  # Write the output to a new column.
  with pytest.raises(Exception):
    dataset.map(_map_fn_1, output_path='map_id', combine_columns=False, num_jobs=num_jobs)

  test_dask_logger.clear_logs()

  dataset.map(
    _map_fn_2, output_path='map_id', combine_columns=False, overwrite=True, num_jobs=num_jobs
  )

  # Map should be called for all ids.
  assert sorted(test_dask_logger.get_logs()) == [0, 1, 2]

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


def test_map_overwrite(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data([{'text': 'a'}, {'text': 'b'}])

  prefix = '0'

  def _map_fn(row: Item, job_id: int) -> Item:
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


def test_map_no_output_col(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data([{'text': 'a sentence'}, {'text': 'b sentence'}])

  signal = TestFirstCharSignal()
  dataset.compute_signal(signal, 'text')

  def _map_fn(row: Item, job_id: int) -> Item:
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


def test_map_explicit_columns(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data([{'text': 'a sentence', 'extra': 1}, {'text': 'b sentence', 'extra': 2}])

  signal = TestFirstCharSignal()
  dataset.compute_signal(signal, 'text')

  def _map_fn(row: Item, job_id: int) -> Item:
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


def test_map_chained(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data([{'text': 'a sentence'}, {'text': 'b sentence'}])

  def _split_fn(row: Item, job_id: int) -> Item:
    return row['text'].split(' ')

  dataset.map(_split_fn, output_path='splits', combine_columns=False)

  def _rearrange_fn(row: Item, job_id: int) -> Item:
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


def test_map_combine_columns(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data([{'text': 'a sentence'}, {'text': 'b sentence'}])

  signal = TestFirstCharSignal()
  dataset.compute_signal(signal, 'text')

  def _map_fn(row: Item, job_id: int) -> Item:
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


def test_signal_on_map_output(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data([{'text': 'abcd'}, {'text': 'efghi'}])

  def _map_fn(row: Item, job_id: int) -> Item:
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

  def _map_fn(row: Item, job_id: int) -> Item:
    return row['text'] + ' ' + row['text']

  with pytest.raises(ValueError, match='Mapping to a nested path is not yet supported'):
    dataset.map(_map_fn, output_path=('double', 'notroot'), combine_columns=False)
