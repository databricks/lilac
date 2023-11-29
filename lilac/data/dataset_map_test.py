"""Tests for dataset.map()."""

import inspect
import re
from typing import ClassVar, Iterable, Literal, Optional

import pytest
from distributed import Client, LocalCluster
from typing_extensions import override

from .. import tasks
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
from .dataset import DatasetManifest, SelectGroupsResult, StatsResult
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

  def _map_fn(item: Item) -> Item:
    return item['text'].upper()

  # Write the output to a new column.
  dataset.map(_map_fn, output_column='text_upper', num_jobs=num_jobs)

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


@pytest.mark.parametrize('num_jobs', [-1, 1, 2])
def test_map_signal(num_jobs: Literal[-1, 1, 2], make_test_data: TestDataMaker) -> None:
  dataset = make_test_data([{'text': 'a sentence'}, {'text': 'b sentence'}])

  signal = TestFirstCharSignal()
  dataset.compute_signal(signal, 'text')

  def _map_fn(item: Item) -> Item:
    return {'result': f'{item["text.test_signal.firstchar"]}_{len(item["text"])}'}

  # Write the output to a new column.
  dataset.map(_map_fn, output_column='output_text', num_jobs=num_jobs)

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

  def _map_fn(item: Item, job_id: int) -> Item:
    test_dask_logger.log_event(job_id)
    return {}

  dataset.map(_map_fn, output_column='map_id', num_jobs=3)

  assert set(test_dask_logger.get_logs()) == set([0, 1, 2])


@pytest.mark.parametrize('num_jobs', [1, 2])
def test_map_input_path(num_jobs: Literal[-1, 1, 2], make_test_data: TestDataMaker) -> None:
  dataset = make_test_data(
    [
      {'id': 0, 'text': 'a'},
      {'id': 1, 'text': 'b'},
      {'id': 2, 'text': 'c'},
    ]
  )

  def _upper(row: Item, job_id: int) -> Item:
    return str(row).upper()

  # Write the output to a new column.
  dataset.map(_upper, input_path='text', output_column='text_upper', num_jobs=num_jobs)

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


@pytest.mark.parametrize('num_jobs', [1, 2])
def test_map_input_path_nested(
  num_jobs: Literal[-1, 1, 2], make_test_data: TestDataMaker, test_dask_logger: TestDaskLogger
) -> None:
  dataset = make_test_data(
    [
      {'id': 0, 'texts': [{'value': 'a'}]},
      {'id': 1, 'texts': [{'value': 'b'}, {'value': 'c'}]},
      {'id': 2, 'texts': [{'value': 'd'}, {'value': 'e'}, {'value': 'f'}]},
    ]
  )

  def _upper(row: Item, job_id: int) -> Item:
    return str(row).upper()

  dataset.map(
    _upper,
    input_path=('texts', PATH_WILDCARD, 'value'),
    output_column='texts_upper',
    num_jobs=num_jobs,
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
    {'id': 0, 'texts.*.value': ['a'], 'texts_upper.*': ['A']},
    {'id': 1, 'texts.*.value': ['b', 'c'], 'texts_upper.*': ['B', 'C']},
    {'id': 2, 'texts.*.value': ['d', 'e', 'f'], 'texts_upper.*': ['D', 'E', 'F']},
  ]


def test_map_input_path_nonleaf_throws(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data(
    [
      {'id': 0, 'text': ['a']},
      {'id': 1, 'text': ['b']},
      {'id': 2, 'text': ['c']},
    ]
  )

  def _upper(row: Item, job_id: int) -> Item:
    return str(row).upper()

  with pytest.raises(Exception):
    dataset.map(_upper, input_path='text', output_column='text_upper')


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

  def _map_fn(item: Item, first_run: bool) -> Item:
    test_dask_logger.log_event(item['id'])

    if first_run and item['id'] == 1:
      raise ValueError('Throwing')

    return item['id']

  def _map_fn_1(item: Item) -> Item:
    return _map_fn(item, first_run=True)

  def _map_fn_2(item: Item) -> Item:
    return _map_fn(item, first_run=False)

  # Write the output to a new column.
  with pytest.raises(Exception):
    dataset.map(_map_fn_1, output_column='map_id', num_jobs=num_jobs)

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

  dataset.map(_map_fn_2, output_column='map_id', num_jobs=num_jobs)

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

  def _map_fn(item: Item, first_run: bool) -> Item:
    test_dask_logger.log_event(item['id'])

    if first_run and item['id'] == 1:
      raise ValueError('Throwing')

    return item['id']

  def _map_fn_1(item: Item) -> Item:
    return _map_fn(item, first_run=True)

  def _map_fn_2(item: Item) -> Item:
    return _map_fn(item, first_run=False)

  # Write the output to a new column.
  with pytest.raises(Exception):
    dataset.map(_map_fn_1, output_column='map_id', num_jobs=num_jobs)

  test_dask_logger.clear_logs()

  dataset.map(_map_fn_2, output_column='map_id', overwrite=True, num_jobs=num_jobs)

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


@pytest.mark.parametrize('num_jobs', [-1, 1, 2])
def test_map_overwrite(num_jobs: Literal[-1, 1, 2], make_test_data: TestDataMaker) -> None:
  dataset = make_test_data([{'text': 'a'}, {'text': 'b'}])

  prefix = '0'

  def _map_fn(item: Item) -> Item:
    nonlocal prefix
    return prefix + item['text']

  # Write the output to a new column.
  dataset.map(_map_fn, output_column='map_text', num_jobs=num_jobs)

  rows = list(dataset.select_rows([PATH_WILDCARD]))
  assert rows == [{'text': 'a', 'map_text': '0a'}, {'text': 'b', 'map_text': '0b'}]

  with pytest.raises(ValueError, match=' which already exists in the dataset'):
    dataset.map(_map_fn, output_column='map_text', combine_columns=False)

  prefix = '1'
  # Overwrite the output
  dataset.map(_map_fn, output_column='map_text', overwrite=True)

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


def test_map_no_output_col(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data([{'text': 'a sentence'}, {'text': 'b sentence'}])

  def _map_fn(item: Item) -> Item:
    return item['text'].upper()

  map_output = dataset.map(_map_fn)

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

  dataset.map(_split_fn, output_column='splits', combine_columns=False)

  def _rearrange_fn(item: Item) -> Item:
    return item['splits.*'][1] + ' ' + item['splits.*'][0]

  dataset.map(_rearrange_fn, output_column='rearrange', combine_columns=False)

  rows = list(dataset.select_rows([PATH_WILDCARD]))
  assert rows == [
    {'text': 'a sentence', 'splits.*': ['a', 'sentence'], 'rearrange': 'sentence a'},
    {'text': 'b sentence', 'splits.*': ['b', 'sentence'], 'rearrange': 'sentence b'},
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

  def _map_fn(item: Item) -> Item:
    # We use the combine_columns=True input here.
    return {'result': f'{item["text"]["test_signal"]["firstchar"]}_{len(item["text"][VALUE_KEY])}'}

  # Write the output to a new column.
  dataset.map(_map_fn, output_column='output_text', combine_columns=True)

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


def test_signal_on_map_output(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data([{'text': 'abcd'}, {'text': 'efghi'}])

  def _map_fn(item: Item) -> Item:
    return item['text'] + ' ' + item['text']

  dataset.map(_map_fn, output_column='double', combine_columns=False)

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


def test_map_nest_under(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data([{'parent': {'text': 'a'}}, {'parent': {'text': 'abc'}}])

  def _map_fn(item: Item) -> Item:
    return {'value': len(item['parent.text'])}

  dataset.map(_map_fn, output_column='len', nest_under=('parent', 'text'))

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

  dataset.map(_map_fn, output_column='b_span', nest_under='text')

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


@pytest.mark.parametrize('num_jobs', [-1, 1, 2])
def test_map_ergonomics(num_jobs: Literal[-1, 1, 2], make_test_data: TestDataMaker) -> None:
  dataset = make_test_data([{'text': 'a sentence'}, {'text': 'b sentence'}])

  def _job_fn_kw(item: Item, job_id: int) -> Item:
    assert job_id is not None
    return item['text'] + ' map'

  def _fn_kw(item: Item) -> Item:
    return item['text'] + ' map'

  def _job_fn(x: Item, jid: int) -> Item:
    assert jid is not None
    return x['text'] + ' map'

  def _fn(x: Item) -> Item:
    return x['text'] + ' map'

  # Write the output to a new column.
  dataset.map(_job_fn_kw, output_column='_job_fn_kw', num_jobs=num_jobs)
  dataset.map(_fn_kw, output_column='_fn_kw', num_jobs=num_jobs)
  dataset.map(_job_fn, output_column='_job_fn', num_jobs=num_jobs)
  dataset.map(_fn, output_column='_fn', num_jobs=num_jobs)

  assert dataset.manifest() == DatasetManifest(
    namespace=TEST_NAMESPACE,
    dataset_name=TEST_DATASET_NAME,
    data_schema=schema(
      {
        'text': 'string',
        '_job_fn_kw': field(
          dtype='string',
          map=MapInfo(
            fn_name='_job_fn_kw',
            fn_source=inspect.getsource(_job_fn_kw),
            date_created=TEST_TIME,
          ),
        ),
        '_fn_kw': field(
          dtype='string',
          map=MapInfo(
            fn_name='_fn_kw', fn_source=inspect.getsource(_fn_kw), date_created=TEST_TIME
          ),
        ),
        '_job_fn': field(
          dtype='string',
          map=MapInfo(
            fn_name='_job_fn',
            fn_source=inspect.getsource(_job_fn),
            date_created=TEST_TIME,
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
      '_job_fn_kw': 'a sentence map',
      '_fn_kw': 'a sentence map',
      '_job_fn': 'a sentence map',
      '_fn': 'a sentence map',
    },
    {
      'text': 'b sentence',
      '_job_fn_kw': 'b sentence map',
      '_fn_kw': 'b sentence map',
      '_job_fn': 'b sentence map',
      '_fn': 'b sentence map',
    },
  ]


@pytest.mark.parametrize('num_jobs', [-1, 1, 2])
def test_map_ergonomics_invalid_args(
  num_jobs: Literal[-1, 1, 2], make_test_data: TestDataMaker
) -> None:
  dataset = make_test_data([{'text': 'a sentence'}, {'text': 'b sentence'}])

  def _map_noargs() -> None:
    pass

  def _map_toomany_args(row: Item, job_id: int, extra_arg: int) -> None:
    pass

  with pytest.raises(ValueError, match=re.escape('Invalid map function')):
    dataset.map(_map_noargs, output_column='_map_noargs', num_jobs=num_jobs)
  with pytest.raises(ValueError, match=re.escape('Invalid map function')):
    dataset.map(_map_toomany_args, output_column='_map_toomany_args', num_jobs=num_jobs)


def test_map_nest_under_validation(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data(
    [{'text': 'abcd', 'parent': ['a', 'b']}, {'text': 'efghi', 'parent': ['c', 'd']}]
  )

  def _map_fn(item: Item) -> Item:
    return item['text'] + ' ' + item['text']

  with pytest.raises(
    ValueError, match='Nesting map outputs under a repeated field is not yet supported'
  ):
    dataset.map(
      _map_fn, output_column='output', nest_under=('parent', PATH_WILDCARD), combine_columns=False
    )

  with pytest.raises(
    ValueError, match=re.escape("The `nest_under` column ('fake',) does not exist.")
  ):
    dataset.map(_map_fn, output_column='output', nest_under=('fake',), combine_columns=False)


def test_map_with_span_resolving(make_test_data: TestDataMaker) -> None:
  dataset = make_test_data([{'text': 'abcd'}, {'text': 'efghi'}])

  def skip_first_and_last_letter(item: str) -> Item:
    return span(1, len(item) - 1)

  dataset.map(skip_first_and_last_letter, input_path='text', output_column='skip')

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
  def text_len(items: Iterable[Item]) -> Iterable[Item]:
    for item in items:
      yield len(item['text'])

  dataset = make_test_data([{'text': 'abcd'}, {'text': 'efghi'}])
  dataset.transform(text_len, output_column='text_len')

  rows = dataset.select_rows()
  assert list(rows) == [{'text': 'abcd', 'text_len': 4}, {'text': 'efghi', 'text_len': 5}]


def test_transform_with_input_path(make_test_data: TestDataMaker) -> None:
  def text_len(texts: Iterable[Item]) -> Iterable[Item]:
    for text in texts:
      yield len(text)

  dataset = make_test_data([{'text': 'abcd'}, {'text': 'efghi'}])
  dataset.transform(text_len, input_path='text', output_column='text_len')

  rows = dataset.select_rows()
  assert list(rows) == [{'text': 'abcd', 'text_len': 4}, {'text': 'efghi', 'text_len': 5}]


def test_transform_size_mismatch(make_test_data: TestDataMaker) -> None:
  def text_len(texts: Iterable[Item]) -> Iterable[Item]:
    for i, text in enumerate(texts):
      # Skip the first item.
      if i > 0:
        yield len(text)

  dataset = make_test_data([{'text': 'abcd'}, {'text': 'efghi'}])
  with pytest.raises(Exception):
    dataset.transform(text_len, input_path='text', output_column='text_len')
