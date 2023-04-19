"""Tests for dataset utils."""
from .dataset_utils import flatten, unflatten


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


def test_unflatten_primitive() -> None:
  original = 'hello'
  result = unflatten(['hello'], original)
  assert result == 'hello'


def test_unflatten_primitive_list() -> None:
  original = ['hello', 'world']
  result = unflatten(['hello', 'world'], original)
  assert result == ['hello', 'world']
