"""Tests for dataset utils."""
from ..schema import PathTuple
from .dataset_utils import flatten, unflatten, wrap_in_dicts


def test_flatten() -> None:
  a = [[1, 2], [[3]], [4, 5, 5]]
  result = flatten(a)
  assert result == [1, 2, 3, 4, 5, 5]


def test_flatten_primitive() -> None:
  result = flatten('hello')
  assert result == ['hello']


def test_unflatten() -> None:
  a = [[1, 2], [[3]], [4, 5, 5]]
  flat_a = flatten(a)
  result = unflatten(flat_a, a)
  assert result == [[1, 2], [[3]], [4, 5, 5]]


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
