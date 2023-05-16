"""Tests for dataset utils."""
from ..schema import UUID_COLUMN, VALUE_KEY, PathTuple
from .dataset_utils import count_primitives, flatten, lilac_items, unflatten, wrap_in_dicts


def test_flatten() -> None:
  a = [[1, 2], [[3]], [4, 5, 5]]
  result = list(flatten(a))
  assert result == [1, 2, 3, 4, 5, 5]


def test_flatten_primitive() -> None:
  result = list(flatten('hello'))
  assert result == ['hello']


def test_unflatten() -> None:
  a = [[1, 2], [[3]], [4, 5, 5]]
  flat_a = list(flatten(a))
  result = unflatten(flat_a, a)
  assert result == [[1, 2], [[3]], [4, 5, 5]]


def test_count_nested() -> None:
  a = [[1, 2], [[3]], [4, 5, 6]]
  assert 6 == count_primitives(a)


def test_wrap_in_dicts_with_spec_of_one_repeated() -> None:
  a = [[1, 2], [3], [4, 5, 5]]
  spec: list[PathTuple] = [('a', 'b', 'c'), ('d',)]  # Corresponds to a.b.c.*.d.
  result = wrap_in_dicts(a, spec)
  assert result == [{
    'a': {
      'b': {
        'c': [{
          'd': 1
        }, {
          'd': 2
        }]
      }
    }
  }, {
    'a': {
      'b': {
        'c': [{
          'd': 3
        }]
      }
    }
  }, {
    'a': {
      'b': {
        'c': [{
          'd': 4
        }, {
          'd': 5
        }, {
          'd': 5
        }]
      }
    }
  }]


def test_wrap_in_dicts_with_spec_of_double_repeated() -> None:
  a = [[[1, 2], [3, 4, 5]], [[6]], [[7], [8], [9, 10]]]
  spec: list[PathTuple] = [('a', 'b'), tuple(), ('c',)]  # Corresponds to a.b.*.*.c.
  result = wrap_in_dicts(a, spec)
  assert result == [{
    'a': {
      'b': [[{
        'c': 1
      }, {
        'c': 2
      }], [{
        'c': 3
      }, {
        'c': 4
      }, {
        'c': 5
      }]]
    }
  }, {
    'a': {
      'b': [[{
        'c': 6
      }]]
    }
  }, {
    'a': {
      'b': [[{
        'c': 7
      }], [{
        'c': 8
      }], [{
        'c': 9
      }, {
        'c': 10
      }]]
    }
  }]


def test_unflatten_primitive() -> None:
  original = 'hello'
  result = unflatten(['hello'], original)
  assert result == 'hello'


def test_unflatten_primitive_list() -> None:
  original = ['hello', 'world']
  result = unflatten(['hello', 'world'], original)
  assert result == ['hello', 'world']


def test_lilac_items() -> None:
  assert lilac_items([{
    UUID_COLUMN: 'uuid',
    'a': 1,
    'b': [2, 3],
    'c': {
      VALUE_KEY: 4
    },
  }, {
    'd': [{
      VALUE_KEY: 5
    }, {
      VALUE_KEY: 6,
      'd_metadata': {
        'd2': 7
      }
    }]
  }]) == [
    {
      # UUID column should remain untouched.
      UUID_COLUMN: 'uuid',
      # Primitives are wrapped deeply.
      'a': {
        VALUE_KEY: 1
      },
      'b': [{
        VALUE_KEY: 2
      }, {
        VALUE_KEY: 3
      }],
      # Primitives that already have value key wrappers should remain untouched.
      'c': {
        VALUE_KEY: 4
      },
    },
    {
      'd': [{
        VALUE_KEY: 5
      }, {
        VALUE_KEY: 6,
        'd_metadata': {
          'd2': {
            VALUE_KEY: 7
          }
        }
      }]
    }
  ]
