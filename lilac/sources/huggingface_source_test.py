"""Tests for the pandas source."""
import os
import pathlib

# mypy: disable-error-code="attr-defined"
from datasets import Dataset, Features, Sequence, Value

from ..schema import schema
from .huggingface_source import HF_SPLIT_COLUMN, HuggingFaceSource
from .source import SourceSchema


def test_hf(tmp_path: pathlib.Path) -> None:
  dataset = Dataset.from_list([{'x': 1, 'y': 'ten'}, {'x': 2, 'y': 'twenty'}])

  dataset_name = os.path.join(tmp_path, 'hf-test-dataset')
  dataset.save_to_disk(dataset_name)

  source = HuggingFaceSource(dataset_name=dataset_name, load_from_disk=True)

  items = source.process()
  source.setup()

  source_schema = source.source_schema()
  assert source_schema == SourceSchema(
    fields=schema({
      HF_SPLIT_COLUMN: 'string',
      'x': 'int64',
      'y': 'string'
    }).fields, num_items=2)

  items = list(source.process())

  assert items == [{
    HF_SPLIT_COLUMN: 'default',
    'x': 1,
    'y': 'ten'
  }, {
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

  source = HuggingFaceSource(dataset_name=dataset_name, load_from_disk=True)

  items = source.process()
  source.setup()

  source_schema = source.source_schema()
  assert source_schema == SourceSchema(
    fields=schema({
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
    HF_SPLIT_COLUMN: 'default',
    'scalar': 1,
    'seq': [1, 0],
    'seq_dict': {
      'x': [1, 2, 3],
      'y': ['four', 'five', 'six']
    }
  }, {
    HF_SPLIT_COLUMN: 'default',
    'scalar': 2,
    'seq': [2, 0],
    'seq_dict': {
      'x': [10, 20, 30],
      'y': ['forty', 'fifty', 'sixty']
    }
  }]


def test_hf_list(tmp_path: pathlib.Path) -> None:
  dataset = Dataset.from_list([{
    'scalar': 1,
    'list': [{
      'x': 1,
      'y': 'two'
    }]
  }, {
    'scalar': 2,
    'list': [{
      'x': 3,
      'y': 'four'
    }]
  }],
                              features=Features({
                                'scalar': Value(dtype='int64'),
                                'list': [{
                                  'x': Value(dtype='int64'),
                                  'y': Value(dtype='string')
                                }]
                              }))

  dataset_name = os.path.join(tmp_path, 'hf-test-dataset')
  dataset.save_to_disk(dataset_name)

  source = HuggingFaceSource(dataset_name=dataset_name, load_from_disk=True)

  items = source.process()
  source.setup()

  source_schema = source.source_schema()
  assert source_schema == SourceSchema(
    fields=schema({
      HF_SPLIT_COLUMN: 'string',
      'scalar': 'int64',
      'list': [{
        'x': 'int64',
        'y': 'string',
      }],
    }).fields,
    num_items=2)

  items = list(source.process())

  assert items == [{
    HF_SPLIT_COLUMN: 'default',
    'scalar': 1,
    'list': [{
      'x': 1,
      'y': 'two'
    }]
  }, {
    HF_SPLIT_COLUMN: 'default',
    'scalar': 2,
    'list': [{
      'x': 3,
      'y': 'four'
    }]
  }]
