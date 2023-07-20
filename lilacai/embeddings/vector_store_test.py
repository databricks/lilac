"""Tests the vector store interface."""

from typing import Type

import numpy as np
import pytest

from .vector_store import VectorStore
from .vector_store_numpy import NumpyVectorStore

ALL_STORES = [NumpyVectorStore]


@pytest.mark.parametrize('store_cls', ALL_STORES)
class VectorStoreSuite:

  def test_get_all(self, store_cls: Type[VectorStore]) -> None:
    store = store_cls()

    store.add([('a',), ('b',), ('c',)], np.array([[1, 2], [3, 4], [5, 6]]))

    np.testing.assert_array_equal(
      store.get([('a',), ('b',), ('c',)]), np.array([[1, 2], [3, 4], [5, 6]]))

  def test_get_subset(self, store_cls: Type[VectorStore]) -> None:
    store = store_cls()

    store.add([('a',), ('b',), ('c',)], np.array([[1, 2], [3, 4], [5, 6]]))

    np.testing.assert_array_equal(store.get([('b',), ('c',)]), np.array([[3, 4], [5, 6]]))

  def test_topk(self, store_cls: Type[VectorStore]) -> None:
    store = store_cls()
    embedding = np.array([[0.45, 0.89], [0.6, 0.8], [0.64, 0.77]])
    query = np.array([0.89, 0.45])
    topk = 3
    store.add([('a',), ('b',), ('c',)], embedding)
    result = store.topk(query, topk)
    assert [key for key, _ in result] == [('c',), ('b',), ('a',)]
    assert [score for _, score in result] == pytest.approx([0.9161, 0.894, 0.801], 1e-3)

  def test_topk_with_restricted_keys(self, store_cls: Type[VectorStore]) -> None:
    store = store_cls()
    embedding = np.array([[0.45, 0.89], [0.6, 0.8], [0.64, 0.77]])
    query = np.array([0.89, 0.45])
    topk = 3
    store.add([('a',), ('b',), ('c',)], embedding)
    result = store.topk(query, topk, key_prefixes=[('b',), ('a',)])
    assert [key for key, _ in result] == [('b',), ('a',)]
    assert [score for _, score in result] == pytest.approx([0.894, 0.801], 1e-3)

    result = store.topk(query, topk, key_prefixes=[('a',), ('b',)])
    assert [key for key, _ in result] == [('b',), ('a',)]
    assert [score for _, score in result] == pytest.approx([0.894, 0.801], 1e-3)

    result = store.topk(query, topk, key_prefixes=[('a',), ('c',)])
    assert [key for key, _ in result] == [('c',), ('a',)]
    assert [score for _, score in result] == pytest.approx([0.9161, 0.801], 1e-3)

  def test_topk_with_key_prefixes(self, store_cls: Type[VectorStore]) -> None:
    store = store_cls()
    embedding = np.array([[8], [9], [3], [10]])
    store.add([('a', 0), ('a', 1), ('b', 0), ('c', 0)], embedding)
    query = np.array([1])
    result = store.topk(query, k=2, key_prefixes=[('b',), ('c',)])
    assert result == [(('c', 0), 10.0), (('b', 0), 3.0)]

    result = store.topk(query, k=10, key_prefixes=[('b',), ('a',)])
    assert result == [(('a', 1), 9.0), (('a', 0), 8.0), (('b', 0), 3.0)]
