"""Tests for the pandas source."""
import os
import pathlib

# mypy: disable-error-code="attr-defined"
from datasets import ClassLabel, Dataset, DatasetDict, Features, Sequence, Value

from ..schema import schema
from ..source import SourceSchema
from ..test_utils import retrieve_parquet_rows
from .huggingface_source import HF_SPLIT_COLUMN, HuggingFaceSource


def test_hf(tmp_path: pathlib.Path) -> None:
  dataset = Dataset.from_list([{'x': 1, 'y': 'ten'}, {'x': 2, 'y': 'twenty'}])

  dataset_name = os.path.join(tmp_path, 'hf-test-dataset')
  dataset.save_to_disk(dataset_name)

  source = HuggingFaceSource(dataset_name=dataset_name, load_from_disk=True)

  source.setup()

  source_schema = source.source_schema()
  assert source_schema == SourceSchema(
    fields=schema({HF_SPLIT_COLUMN: 'string', 'x': 'int64', 'y': 'string'}).fields, num_items=2
  )

  manifest = source.load_to_parquet(str(tmp_path), task_step_id=None)
  items = retrieve_parquet_rows(tmp_path, manifest)

  assert items == [
    {HF_SPLIT_COLUMN: 'default', 'x': 1, 'y': 'ten'},
    {HF_SPLIT_COLUMN: 'default', 'x': 2, 'y': 'twenty'},
  ]


def test_hf_splits(tmp_path: pathlib.Path) -> None:
  dataset = Dataset.from_list(
    [{'x': 1, 'y': 'ten'}, {'x': 2, 'y': 'twenty'}, {'x': 3, 'y': 'thirty'}]
  )
  dataset_splits = DatasetDict({'train': dataset, 'test': dataset})

  dataset_name = os.path.join(tmp_path, 'hf-test-dataset')
  dataset_splits.save_to_disk(dataset_name)

  source = HuggingFaceSource(dataset_name=dataset_name, load_from_disk=True, sample_size=2)

  source.setup()

  source_schema = source.source_schema()
  assert source_schema == SourceSchema(
    fields=schema({HF_SPLIT_COLUMN: 'string', 'x': 'int64', 'y': 'string'}).fields, num_items=4
  )

  manifest = source.load_to_parquet(str(tmp_path), task_step_id=None)
  items = retrieve_parquet_rows(tmp_path, manifest)

  assert items == [
    {HF_SPLIT_COLUMN: 'train', 'x': 1, 'y': 'ten'},
    {HF_SPLIT_COLUMN: 'train', 'x': 2, 'y': 'twenty'},
    {HF_SPLIT_COLUMN: 'test', 'x': 1, 'y': 'ten'},
    {HF_SPLIT_COLUMN: 'test', 'x': 2, 'y': 'twenty'},
  ]


def test_hf_sequence(tmp_path: pathlib.Path) -> None:
  dataset = Dataset.from_list(
    [
      {'scalar': 1, 'seq': [1, 0], 'seq_dict': {'x': [1, 2, 3], 'y': ['four', 'five', 'six']}},
      {
        'scalar': 2,
        'seq': [2, 0],
        'seq_dict': {'x': [10, 20, 30], 'y': ['forty', 'fifty', 'sixty']},
      },
    ],
    features=Features(
      {
        'scalar': Value(dtype='int64'),
        'seq': Sequence(feature=Value(dtype='int64')),
        'seq_dict': Sequence(feature={'x': Value(dtype='int64'), 'y': Value(dtype='string')}),
      }
    ),
  )

  dataset_name = os.path.join(tmp_path, 'hf-test-dataset')
  dataset.save_to_disk(dataset_name)

  source = HuggingFaceSource(dataset_name=dataset_name, load_from_disk=True)

  source.setup()

  source_schema = source.source_schema()
  assert source_schema == SourceSchema(
    fields=schema(
      {
        HF_SPLIT_COLUMN: 'string',
        'scalar': 'int64',
        'seq': ['int64'],
        'seq_dict': {'x': ['int64'], 'y': ['string']},
      }
    ).fields,
    num_items=2,
  )

  manifest = source.load_to_parquet(str(tmp_path), task_step_id=None)
  items = retrieve_parquet_rows(tmp_path, manifest)

  assert items == [
    {
      HF_SPLIT_COLUMN: 'default',
      'scalar': 1,
      'seq': [1, 0],
      'seq_dict': {'x': [1, 2, 3], 'y': ['four', 'five', 'six']},
    },
    {
      HF_SPLIT_COLUMN: 'default',
      'scalar': 2,
      'seq': [2, 0],
      'seq_dict': {'x': [10, 20, 30], 'y': ['forty', 'fifty', 'sixty']},
    },
  ]


def test_hf_list(tmp_path: pathlib.Path) -> None:
  dataset = Dataset.from_list(
    [{'scalar': 1, 'list': [{'x': 1, 'y': 'two'}]}, {'scalar': 2, 'list': [{'x': 3, 'y': 'four'}]}],
    features=Features(
      {
        'scalar': Value(dtype='int64'),
        'list': [{'x': Value(dtype='int64'), 'y': Value(dtype='string')}],
      }
    ),
  )

  dataset_name = os.path.join(tmp_path, 'hf-test-dataset')
  dataset.save_to_disk(dataset_name)

  source = HuggingFaceSource(dataset_name=dataset_name, load_from_disk=True)

  source.setup()

  source_schema = source.source_schema()
  assert source_schema == SourceSchema(
    fields=schema(
      {HF_SPLIT_COLUMN: 'string', 'scalar': 'int64', 'list': [{'x': 'int64', 'y': 'string'}]}
    ).fields,
    num_items=2,
  )

  manifest = source.load_to_parquet(str(tmp_path), task_step_id=None)
  items = retrieve_parquet_rows(tmp_path, manifest)

  assert items == [
    {HF_SPLIT_COLUMN: 'default', 'scalar': 1, 'list': [{'x': 1, 'y': 'two'}]},
    {HF_SPLIT_COLUMN: 'default', 'scalar': 2, 'list': [{'x': 3, 'y': 'four'}]},
  ]


def test_hf_class_labels(tmp_path: pathlib.Path) -> None:
  dataset = Dataset.from_list(
    [{'x': 1, 'y': 'ten'}, {'x': 2, 'y': 'twenty'}],
    features=Features(
      {
        'x': ClassLabel(num_classes=3, names=['x0', 'x1', 'x2']),
        'y': Value(dtype='string'),
      }
    ),
  )
  dataset_name = os.path.join(tmp_path, 'hf-test-dataset')
  dataset.save_to_disk(dataset_name)

  source = HuggingFaceSource(dataset_name=dataset_name, load_from_disk=True)
  source.setup()

  source_schema = source.source_schema()
  assert source_schema == SourceSchema(
    fields=schema({HF_SPLIT_COLUMN: 'string', 'x': 'string', 'y': 'string'}).fields, num_items=2
  )

  manifest = source.load_to_parquet(str(tmp_path), task_step_id=None)
  items = retrieve_parquet_rows(tmp_path, manifest)

  assert items == [
    {HF_SPLIT_COLUMN: 'default', 'x': 'x1', 'y': 'ten'},
    {HF_SPLIT_COLUMN: 'default', 'x': 'x2', 'y': 'twenty'},
  ]
