"""Tests for the pandas source."""
import os
import pathlib

# mypy: disable-error-code="attr-defined"
from datasets import Dataset, Features, Sequence, Value

from ...schema import UUID_COLUMN, schema
from .huggingface_source import HF_SPLIT_COLUMN, HuggingFaceDataset
from .source import SourceSchema


def test_hf(tmp_path: pathlib.Path) -> None:
  dataset = Dataset.from_list([{'x': 1, 'y': 'ten'}, {'x': 2, 'y': 'twenty'}])

  dataset_name = os.path.join(tmp_path, 'hf-test-dataset')
  dataset.save_to_disk(dataset_name)

  source = HuggingFaceDataset(dataset_name=dataset_name, load_from_disk=True)

  items = source.process()
  source.prepare()

  source_schema = source.source_schema()
  assert source_schema == SourceSchema(
    fields=schema({
      UUID_COLUMN: 'string',
      HF_SPLIT_COLUMN: 'string',
      'x': 'int64',
      'y': 'string'
    }).fields,
    num_items=2)

  items = list(source.process())

  assert items == [{
    UUID_COLUMN: '0',
    HF_SPLIT_COLUMN: 'default',
    'x': 1,
    'y': 'ten'
  }, {
    UUID_COLUMN: '1',
    HF_SPLIT_COLUMN: 'default',
    'x': 2,
    'y': 'twenty'
  }]


def test_hf_sequence(tmp_path: pathlib.Path) -> None:
  dataset = Dataset.from_list([{
    'scalar': 1,
    'seq': [1, 0],
    'seq_dict': {
      'x': [1, 2, 3],
      'y': ['four', 'five', 'six']
    }
  }, {
    'scalar': 2,
    'seq': [2, 0],
    'seq_dict': {
      'x': [10, 20, 30],
      'y': ['forty', 'fifty', 'sixty']
    }
  }],
                              features=Features({
                                'scalar': Value(dtype='int64'),
                                'seq': Sequence(feature=Value(dtype='int64')),
                                'seq_dict': Sequence(feature={
                                  'x': Value(dtype='int64'),
                                  'y': Value(dtype='string')
                                })
                              }))

  dataset_name = os.path.join(tmp_path, 'hf-test-dataset')
  dataset.save_to_disk(dataset_name)

  source = HuggingFaceDataset(dataset_name=dataset_name, load_from_disk=True)

  items = source.process()
  source.prepare()

  source_schema = source.source_schema()
  assert source_schema == SourceSchema(
    fields=schema({
      UUID_COLUMN: 'string',
      HF_SPLIT_COLUMN: 'string',
      'scalar': 'int64',
      'seq': ['int64'],
      'seq_dict': {
        'x': ['int64'],
        'y': ['string'],
      },
    }).fields,
    num_items=2)

  items = list(source.process())

  assert items == [{
    UUID_COLUMN: '0',
    HF_SPLIT_COLUMN: 'default',
    'scalar': 1,
    'seq': [1, 0],
    'seq_dict': {
      'x': [1, 2, 3],
      'y': ['four', 'five', 'six']
    }
  }, {
    UUID_COLUMN: '1',
    HF_SPLIT_COLUMN: 'default',
    'scalar': 2,
    'seq': [2, 0],
    'seq_dict': {
      'x': [10, 20, 30],
      'y': ['forty', 'fifty', 'sixty']
    }
  }]
