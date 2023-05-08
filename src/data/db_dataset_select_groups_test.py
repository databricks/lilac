"""Tests for db.select_groups()."""

import pathlib
import re
from typing import Generator, Type

import pandas as pd
import pytest
from pytest_mock import MockerFixture

from ..config import CONFIG
from ..schema import UUID_COLUMN, Item, schema
from . import db_dataset
from .db_dataset import DatasetDB, NamedBins
from .db_dataset_duckdb import DatasetDuckDB
from .db_dataset_test_utils import make_db

ALL_DBS = [DatasetDuckDB]


@pytest.fixture(autouse=True)
def set_data_path(tmp_path: pathlib.Path) -> Generator:
  data_path = CONFIG['LILAC_DATA_PATH']
  CONFIG['LILAC_DATA_PATH'] = str(tmp_path)
  yield
  CONFIG['LILAC_DATA_PATH'] = data_path or ''


@pytest.mark.parametrize('db_cls', ALL_DBS)
class SelectGroupsSuite:

  def test_flat_data(self, tmp_path: pathlib.Path, db_cls: Type[DatasetDB]) -> None:
    items: list[Item] = [
      {
        'name': 'Name1',
        'age': 34,
        'active': False
      },
      {
        'name': 'Name2',
        'age': 45,
        'active': True
      },
      {
        'age': 17,
        'active': True
      },  # Missing "name".
      {
        'name': 'Name3',
        'active': True
      },  # Missing "age".
      {
        'name': 'Name4',
        'age': 55
      }  # Missing "active".
    ]
    db = make_db(
      db_cls=db_cls,
      tmp_path=tmp_path,
      items=items,
      schema=schema({
        UUID_COLUMN: 'string',
        'name': 'string',
        'age': 'int32',
        'active': 'boolean'
      }))

    result = db.select_groups(leaf_path='name').df()
    expected = pd.DataFrame.from_records([{
      'value': 'Name1',
      'count': 1
    }, {
      'value': 'Name2',
      'count': 1
    }, {
      'value': None,
      'count': 1
    }, {
      'value': 'Name3',
      'count': 1
    }, {
      'value': 'Name4',
      'count': 1
    }])
    pd.testing.assert_frame_equal(result, expected)

    result = db.select_groups(leaf_path='age', bins=[20, 50, 60]).df()
    expected = pd.DataFrame.from_records([
      {
        'value': 1,  # age 20-50.
        'count': 2
      },
      {
        'value': 0,  # age < 20.
        'count': 1
      },
      {
        'value': None,  # Missing age.
        'count': 1
      },
      {
        'value': 2,  # age 50-60.
        'count': 1
      }
    ])
    pd.testing.assert_frame_equal(result, expected)

    result = db.select_groups(leaf_path='active').df()
    expected = pd.DataFrame.from_records([
      {
        'value': True,
        'count': 3
      },
      {
        'value': False,
        'count': 1
      },
      {
        'value': None,  # Missing "active".
        'count': 1
      }
    ])
    pd.testing.assert_frame_equal(result, expected)

  def test_result_is_iterable(self, tmp_path: pathlib.Path, db_cls: Type[DatasetDB]) -> None:
    items: list[Item] = [
      {
        'active': False
      },
      {
        'active': True
      },
      {
        'active': True
      },
      {
        'active': True
      },
      {}  # Missing "active".
    ]
    db = make_db(
      db_cls=db_cls,
      tmp_path=tmp_path,
      items=items,
      schema=schema({
        UUID_COLUMN: 'string',
        'active': 'boolean'
      }))

    result = db.select_groups(leaf_path='active')
    groups = list(result)
    assert groups == [(True, 3), (False, 1), (None, 1)]

  def test_list_of_structs(self, tmp_path: pathlib.Path, db_cls: Type[DatasetDB]) -> None:
    items: list[Item] = [{
      'list_of_structs': [{
        'name': 'a'
      }, {
        'name': 'b'
      }]
    }, {
      'list_of_structs': [{
        'name': 'c'
      }, {
        'name': 'a'
      }, {
        'name': 'd'
      }]
    }, {
      'list_of_structs': [{
        'name': 'd'
      }]
    }]
    db = make_db(
      db_cls=db_cls,
      tmp_path=tmp_path,
      items=items,
      schema=schema({
        UUID_COLUMN: 'string',
        'list_of_structs': [{
          'name': 'string'
        }],
      }))

    result = db.select_groups(leaf_path='list_of_structs.*.name').df()
    expected = pd.DataFrame.from_records([{
      'value': 'a',
      'count': 2
    }, {
      'value': 'd',
      'count': 2
    }, {
      'value': 'b',
      'count': 1
    }, {
      'value': 'c',
      'count': 1
    }])
    pd.testing.assert_frame_equal(result, expected)

  def test_nested_lists(self, tmp_path: pathlib.Path, db_cls: Type[DatasetDB]) -> None:
    items: list[Item] = [{
      'nested_list': [[{
        'name': 'a'
      }], [{
        'name': 'b'
      }]]
    }, {
      'nested_list': [[{
        'name': 'c'
      }, {
        'name': 'a'
      }], [{
        'name': 'd'
      }]]
    }, {
      'nested_list': [[{
        'name': 'd'
      }]]
    }]
    db = make_db(
      db_cls=db_cls,
      tmp_path=tmp_path,
      items=items,
      schema=schema({
        UUID_COLUMN: 'string',
        'nested_list': [[{
          'name': 'string'
        }]]
      }))

    result = db.select_groups(leaf_path='nested_list.*.*.name').df()
    expected = pd.DataFrame.from_records([{
      'value': 'a',
      'count': 2
    }, {
      'value': 'd',
      'count': 2
    }, {
      'value': 'b',
      'count': 1
    }, {
      'value': 'c',
      'count': 1
    }])
    pd.testing.assert_frame_equal(result, expected)

  def test_nested_struct(self, tmp_path: pathlib.Path, db_cls: Type[DatasetDB]) -> None:
    items: list[Item] = [
      {
        'nested_struct': {
          'struct': {
            'name': 'c'
          }
        }
      },
      {
        'nested_struct': {
          'struct': {
            'name': 'b'
          }
        }
      },
      {
        'nested_struct': {
          'struct': {
            'name': 'a'
          }
        }
      },
    ]
    db = make_db(
      db_cls=db_cls,
      tmp_path=tmp_path,
      items=items,
      schema=schema({
        UUID_COLUMN: 'string',
        'nested_struct': {
          'struct': {
            'name': 'string'
          }
        },
      }))

    result = db.select_groups(leaf_path='nested_struct.struct.name').df()
    expected = pd.DataFrame.from_records([{
      'value': 'c',
      'count': 1
    }, {
      'value': 'b',
      'count': 1
    }, {
      'value': 'a',
      'count': 1
    }])
    pd.testing.assert_frame_equal(result, expected)

  def test_named_bins(self, tmp_path: pathlib.Path, db_cls: Type[DatasetDB]) -> None:
    items: list[Item] = [{
      'age': 34,
    }, {
      'age': 45,
    }, {
      'age': 17,
    }, {
      'age': 80
    }, {
      'age': 55
    }]
    db = make_db(
      db_cls=db_cls,
      tmp_path=tmp_path,
      items=items,
      schema=schema({
        UUID_COLUMN: 'string',
        'age': 'int32',
      }))

    result = db.select_groups(
      leaf_path='age',
      bins=NamedBins(bins=[20, 50, 65], labels=['young', 'adult', 'middle-aged', 'senior'])).df()
    expected = pd.DataFrame.from_records([
      {
        'value': 'adult',  # age 20-50.
        'count': 2
      },
      {
        'value': 'young',  # age < 20.
        'count': 1
      },
      {
        'value': 'senior',  # age > 65.
        'count': 1
      },
      {
        'value': 'middle-aged',  # age 50-65.
        'count': 1
      }
    ])
    pd.testing.assert_frame_equal(result, expected)

  def test_invalid_leaf(self, tmp_path: pathlib.Path, db_cls: Type[DatasetDB]) -> None:
    items: list[Item] = [
      {
        'nested_struct': {
          'struct': {
            'name': 'c'
          }
        }
      },
      {
        'nested_struct': {
          'struct': {
            'name': 'b'
          }
        }
      },
      {
        'nested_struct': {
          'struct': {
            'name': 'a'
          }
        }
      },
    ]
    db = make_db(
      db_cls=db_cls,
      tmp_path=tmp_path,
      items=items,
      schema=schema({
        UUID_COLUMN: 'string',
        'nested_struct': {
          'struct': {
            'name': 'string'
          }
        },
      }))

    with pytest.raises(
        ValueError, match=re.escape("Leaf \"('nested_struct',)\" not found in dataset")):
      db.select_groups(leaf_path='nested_struct')

    with pytest.raises(
        ValueError, match=re.escape("Leaf \"('nested_struct', 'struct')\" not found in dataset")):
      db.select_groups(leaf_path='nested_struct.struct')

    with pytest.raises(
        ValueError,
        match=re.escape("Leaf \"('nested_struct', 'struct', 'wrong_name')\" not found in dataset")):
      db.select_groups(leaf_path='nested_struct.struct.wrong_name')

  def test_too_many_distinct(self, tmp_path: pathlib.Path, db_cls: Type[DatasetDB],
                             mocker: MockerFixture) -> None:
    too_many_distinct = 5
    mocker.patch(f'{db_dataset.__name__}.TOO_MANY_DISTINCT', too_many_distinct)

    items: list[Item] = [{'feature': str(i)} for i in range(too_many_distinct + 10)]
    db = make_db(
      db_cls=db_cls,
      tmp_path=tmp_path,
      items=items,
      schema=schema({
        UUID_COLUMN: 'string',
        'feature': 'string'
      }))

    with pytest.raises(
        ValueError, match=re.escape('Leaf "(\'feature\',)" has too many unique values: 15')):
      db.select_groups('feature')

  def test_bins_are_required_for_float(self, tmp_path: pathlib.Path,
                                       db_cls: Type[DatasetDB]) -> None:
    items: list[Item] = [{'feature': float(i)} for i in range(5)]
    db = make_db(
      db_cls=db_cls,
      tmp_path=tmp_path,
      items=items,
      schema=schema({
        UUID_COLUMN: 'string',
        'feature': 'float32'
      }))

    with pytest.raises(
        ValueError,
        match=re.escape('"bins" needs to be defined for the int/float leaf "(\'feature\',)"')):
      db.select_groups('feature')
