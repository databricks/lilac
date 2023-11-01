"""Tests for dataset utils."""

from typing import Iterable, Iterator

from ..schema import PathTuple
from ..utils import chunks
from .dataset_utils import count_primitives, sparse_to_dense_compute, wrap_in_dicts


def test_count_nested() -> None:
  a = [[1, 2], [[3]], [4, 5, 6]]
  assert 6 == count_primitives(a)


def test_wrap_in_dicts_with_spec_of_one_repeated() -> None:
  a = [[1, 2], [3], [4, 5, 5]]
  spec: list[PathTuple] = [('a', 'b', 'c'), ('d',)]  # Corresponds to a.b.c.*.d.
  result = wrap_in_dicts(a, spec)
  assert list(result) == [
    {'a': {'b': {'c': [{'d': 1}, {'d': 2}]}}},
    {'a': {'b': {'c': [{'d': 3}]}}},
    {'a': {'b': {'c': [{'d': 4}, {'d': 5}, {'d': 5}]}}},
  ]


def test_wrap_in_dicts_with_spec_of_double_repeated() -> None:
  a = [[[1, 2], [3, 4, 5]], [[6]], [[7], [8], [9, 10]]]
  spec: list[PathTuple] = [('a', 'b'), tuple(), ('c',)]  # Corresponds to a.b.*.*.c.
  result = wrap_in_dicts(a, spec)
  assert list(result) == [
    {'a': {'b': [[{'c': 1}, {'c': 2}], [{'c': 3}, {'c': 4}, {'c': 5}]]}},
    {'a': {'b': [[{'c': 6}]]}},
    {'a': {'b': [[{'c': 7}], [{'c': 8}], [{'c': 9}, {'c': 10}]]}},
  ]


def test_sparse_to_dense_compute() -> None:
  sparse_input = iter([None, 1, 7, None, None, 3, None, 5, None, None])

  def func(xs: Iterable[int]) -> Iterable[int]:
    for x in xs:
      yield x + 1

  out = sparse_to_dense_compute(sparse_input, func)
  assert list(out) == [None, 2, 8, None, None, 4, None, 6, None, None]


def test_sparse_to_dense_compute_batching() -> None:
  sparse_input = iter([None, 1, 7, None, None, 3, None, 5, None, None])

  def func(xs: Iterable[int]) -> Iterable[int]:
    for batch in chunks(xs, 2):
      yield batch[0] + 1
      if len(batch) > 1:
        yield batch[1] + 1

  out = sparse_to_dense_compute(sparse_input, func)
  assert list(out) == [None, 2, 8, None, None, 4, None, 6, None, None]


def test_fully_dense() -> None:
  sparse_input = iter([1, 7, 3, 5])

  def func(xs: Iterable[int]) -> Iterable[int]:
    for x in xs:
      yield x + 1

  out = sparse_to_dense_compute(sparse_input, func)
  assert list(out) == [2, 8, 4, 6]


def test_sparse_to_dense_compute_fully_sparse() -> None:
  sparse_input = iter([None, None, None])

  def func(xs: Iterable[int]) -> Iterable[int]:
    for x in xs:
      yield x + 1

  out = sparse_to_dense_compute(sparse_input, func)
  assert list(out) == [None, None, None]


def test_sparse_to_dense_compute_empty() -> None:
  sparse_input: Iterator[int] = iter([])

  def func(xs: Iterable[int]) -> Iterable[int]:
    for x in xs:
      yield x + 1

  out = sparse_to_dense_compute(sparse_input, func)
  assert list(out) == []
