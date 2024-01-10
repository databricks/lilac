"""Test batch_utils.py."""
import itertools
from typing import Iterable

import numpy as np

from .batch_utils import (
  flat_batched_compute,
  flatten,
  flatten_iter,
  flatten_path_iter,
  unflatten,
  unflatten_iter,
)


def test_batched_compute() -> None:
  input = [[1], [2, 3], [4, 5]]
  batch_size = 2  # Does not evenly split any input

  def f(inputs: Iterable[int]) -> list[int]:
    return [x * x for x in inputs]

  assert list(flat_batched_compute(input, f, batch_size)) == [[1], [4, 9], [16, 25]]


def test_batched_compute_np() -> None:
  input = [
    [np.array([1, 1])],
    [np.array([2, 2]), np.array([3, 3])],
    [np.array([4, 4]), np.array([5, 5])],
  ]
  batch_size = 2  # Does not evenly split any input

  def f(inputs: Iterable[np.ndarray]) -> Iterable[float]:
    return [x[0] * x[0] for x in inputs]

  assert list(flat_batched_compute(input, f, batch_size)) == [[1], [4, 9], [16, 25]]


def test_flatten() -> None:
  a = [[1, 2], [3], [4, 5, 5]]
  result = list(flatten(a))
  assert result == [1, 2, 3, 4, 5, 5]


def test_unflatten() -> None:
  a = [[1, 2], [3], [4, 5, 5]]
  flat_a = list(flatten(a))
  result = list(unflatten(flat_a, a))
  assert result == [[1, 2], [3], [4, 5, 5]]


def test_deep_flatten() -> None:
  a = [[1, 2], [[3]], [4, 5, [5]]]
  result = list(flatten_iter(a))
  assert result == [1, 2, 3, 4, 5, 5]


def test_deep_flatten_np() -> None:
  input = [[np.array([1, 1])], [np.array([2, 2]), np.array([3, 3])]]
  result = list(flatten_iter(input))

  assert len(result) == 3
  np.testing.assert_array_equal(result[0], np.array([1, 1]))
  np.testing.assert_array_equal(result[1], np.array([2, 2]))
  np.testing.assert_array_equal(result[2], np.array([3, 3]))


def test_deep_unflatten() -> None:
  a = [[1, 2], [[3]], [4, 5, 5]]
  flat_a = list(flatten_iter(a))
  flat_f_a = [a * 2 for a in flat_a]
  result = list(unflatten_iter(flat_f_a, a))
  assert result == [[2, 4], [[6]], [8, 10, 10]]


def test_deep_unflatten_generator() -> None:
  a = ([1, 2], [[3]], [4, 5, 5])
  a_0, a_1 = itertools.tee(a, 2)
  flat_a = list(flatten_iter(a_0))
  flat_f_a = [a * 2 for a in flat_a]
  result = list(unflatten_iter(flat_f_a, a_1))
  assert result == [[2, 4], [[6]], [8, 10, 10]]


def test_deep_unflatten_primitive() -> None:
  original = 'hello'
  result = next(iter(unflatten_iter(['hello'], original)))
  assert result == 'hello'


def test_deep_unflatten_primitive_list() -> None:
  original = ['hello', 'world']
  result = list(unflatten_iter(['hello', 'world'], original))
  assert result == ['hello', 'world']


def test_deep_unflatten_np() -> None:
  input = [[np.array([1, 1])], [np.array([2, 2]), np.array([3, 3])]]
  result = list(unflatten_iter(flatten_iter(input), input))

  assert len(result) == 2
  np.testing.assert_array_equal(result[0], [np.array([1, 1])])
  np.testing.assert_array_equal(result[1], [np.array([2, 2]), np.array([3, 3])])


def test_flatten_path_iter() -> None:
  input = [
    {'names': [{'first': 'John', 'last': 'Doe'}, {'first': 'Jane', 'last': 'Doe'}]},
    {'names': [{'first': 'Blake', 'last': 'Smith'}, {'first': 'Rob', 'last': 'Smith'}]},
  ]
  result = list(flatten_path_iter(input, path=('*', 'names', '*', 'first')))
  assert result == ['John', 'Jane', 'Blake', 'Rob']

  result = list(flatten_path_iter(input, path=('*', 'names', '*')))
  assert result == [
    {'first': 'John', 'last': 'Doe'},
    {'first': 'Jane', 'last': 'Doe'},
    {'first': 'Blake', 'last': 'Smith'},
    {'first': 'Rob', 'last': 'Smith'},
  ]
  result = list(flatten_path_iter(input, path=('*', 'names')))
  assert result == [
    [{'first': 'John', 'last': 'Doe'}, {'first': 'Jane', 'last': 'Doe'}],
    [{'first': 'Blake', 'last': 'Smith'}, {'first': 'Rob', 'last': 'Smith'}],
  ]

  result = list(flatten_path_iter(input, path=tuple('*')))
  assert result == [
    {'names': [{'first': 'John', 'last': 'Doe'}, {'first': 'Jane', 'last': 'Doe'}]},
    {'names': [{'first': 'Blake', 'last': 'Smith'}, {'first': 'Rob', 'last': 'Smith'}]},
  ]
