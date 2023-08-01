"""Test utils.py."""
from typing import Iterable

import numpy as np

from .batch_utils import flat_batched_compute, flatten, unflatten


def test_batched_compute() -> None:
  input = [[1], [2, 3], [4, 5]]
  batch_size = 2  # Does not evenly split any input

  def f(inputs: Iterable[int]) -> list[int]:
    return [x * x for x in inputs]

  assert flat_batched_compute(input, f, batch_size) == [[1], [4, 9], [16, 25]]


def test_batched_compute_np() -> None:
  input = [[np.array([1, 1])], [np.array([2, 2]), np.array([3, 3])],
           [np.array([4, 4]), np.array([5, 5])]]
  batch_size = 2  # Does not evenly split any input

  def f(inputs: Iterable[np.ndarray]) -> Iterable[float]:
    return [x[0] * x[0] for x in inputs]

  assert flat_batched_compute(input, f, batch_size) == [[1], [4, 9], [16, 25]]


def test_flatten() -> None:
  a = [[1, 2], [[3]], [4, 5, 5]]
  result = list(flatten(a))
  assert result == [1, 2, 3, 4, 5, 5]


def test_flatten_primitive() -> None:
  result = list(flatten('hello'))
  assert result == ['hello']


def test_flatten_np() -> None:
  input = [
    [np.array([1, 1])],
    [np.array([2, 2]), np.array([3, 3])],
  ]
  result = list(flatten(input))

  assert len(result) == 3
  np.testing.assert_array_equal(result[0], np.array([1, 1]))
  np.testing.assert_array_equal(result[1], np.array([2, 2]))
  np.testing.assert_array_equal(result[2], np.array([3, 3]))


def test_unflatten() -> None:
  a = [[1, 2], [[3]], [4, 5, 5]]
  flat_a = list(flatten(a))
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


def test_unflatten_np() -> None:
  input = [
    [np.array([1, 1])],
    [np.array([2, 2]), np.array([3, 3])],
  ]
  result = list(unflatten(flatten(input), input))

  assert len(result) == 2
  np.testing.assert_array_equal(result[0], [np.array([1, 1])])
  np.testing.assert_array_equal(result[1], [np.array([2, 2]), np.array([3, 3])])
