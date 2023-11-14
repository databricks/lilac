"""Tests the vector store interface."""

import pathlib
from typing import Type, cast

import numpy as np
import pytest
from sklearn.preprocessing import normalize

from .vector_store import VectorDBIndex, VectorStore
from .vector_store_hnsw import HNSWVectorStore
from .vector_store_numpy import NumpyVectorStore

ALL_STORES = [NumpyVectorStore, HNSWVectorStore]


@pytest.mark.parametrize('store_cls', ALL_STORES)
class VectorStoreImplSuite:
  def test_add_chunks(self, store_cls: Type[VectorStore]) -> None:
    store = store_cls()

    store.add([('a',), ('b',)], np.array([[1, 2], [3, 4]]))
    store.add([('c',)], np.array([[5, 6]]))

    np.testing.assert_array_equal(
      store.get([('a',), ('b',), ('c',)]), np.array([[1, 2], [3, 4], [5, 6]])
    )

  def test_get_all(self, store_cls: Type[VectorStore]) -> None:
    store = store_cls()

    store.add([('a',), ('b',), ('c',)], np.array([[1, 2], [3, 4], [5, 6]]))

    np.testing.assert_array_equal(
      store.get([('a',), ('b',), ('c',)]), np.array([[1, 2], [3, 4], [5, 6]])
    )

  def test_get_subset(self, store_cls: Type[VectorStore]) -> None:
    store = store_cls()

    store.add([('a',), ('b',), ('c',)], np.array([[1, 2], [3, 4], [5, 6]]))

    np.testing.assert_array_equal(store.get([('b',), ('c',)]), np.array([[3, 4], [5, 6]]))

  def test_save_load(self, store_cls: Type[VectorStore], tmp_path: pathlib.Path) -> None:
    store = store_cls()

    store.add([('a',), ('b',), ('c',)], np.array([[1, 2], [3, 4], [5, 6]]))

    store.save(str(tmp_path))

    del store

    store = store_cls()
    store.load((str(tmp_path)))

    np.testing.assert_array_equal(
      store.get([('a',), ('b',), ('c',)]), np.array([[1, 2], [3, 4], [5, 6]])
    )

  def test_topk(self, store_cls: Type[VectorStore]) -> None:
    store = store_cls()
    embedding = cast(np.ndarray, normalize(np.array([[1, 0], [0, 1], [1, 1]])))
    query = np.array([0.9, 1])
    query /= np.linalg.norm(query)
    topk = 3
    store.add([('a',), ('b',), ('c',)], embedding)
    result = store.topk(query, topk)
    assert [key for key, _ in result] == [('c',), ('b',), ('a',)]
    assert [score for _, score in result] == pytest.approx([0.999, 0.743, 0.669], abs=1e-3)

  def test_topk_with_restricted_keys(self, store_cls: Type[VectorStore]) -> None:
    store = store_cls()
    embedding = np.array([[0.45, 0.89], [0.6, 0.8], [0.64, 0.77]])
    query = np.array([0.89, 0.45])
    topk = 3
    store.add([('a',), ('b',), ('c',)], embedding)
    result = store.topk(query, topk, keys=[('b',), ('a',)])
    assert [key for key, _ in result] == [('b',), ('a',)]
    assert [score for _, score in result] == pytest.approx([0.894, 0.801], 1e-3)

    result = store.topk(query, topk, keys=[('a',), ('b',)])
    assert [key for key, _ in result] == [('b',), ('a',)]
    assert [score for _, score in result] == pytest.approx([0.894, 0.801], 1e-3)

    result = store.topk(query, topk, keys=[('a',), ('c',)])
    assert [key for key, _ in result] == [('c',), ('a',)]
    assert [score for _, score in result] == pytest.approx([0.9161, 0.801], 1e-3)

  def test_topk_with_keys(self, store_cls: Type[VectorStore]) -> None:
    store = store_cls()
    embedding = np.array([[8], [9], [3], [10]])
    store.add([('a', 0), ('a', 1), ('b', 0), ('c', 0)], embedding)
    query = np.array([1])
    result = store.topk(query, k=2, keys=[('b', 0), ('c', 0)])
    assert result == [(('c', 0), 10.0), (('b', 0), 3.0)]

    result = store.topk(query, k=10, keys=[('b', 0), ('a', 1), ('a', 0)])
    assert result == [(('a', 1), 9.0), (('a', 0), 8.0), (('b', 0), 3.0)]


class VectorStoreWrapperSuite:
  def test_topk_with_missing_keys(self) -> None:
    store = VectorDBIndex('numpy')
    all_spans = [
      (('a',), [(0, 1), (2, 3)]),
      (('b',), [(0, 1), (2, 3)]),
      (('c',), [(0, 1), (2, 3)]),
    ]
    embedding = np.array([[8], [9], [3], [10], [11], [12]])
    store.add(all_spans, embedding)

    query = np.array([1])
    result = store.topk(query, k=2, rowids=['a', 'b', 'c', 'd'])
    assert result == [(('c',), 12.0), (('b',), 10.0)]
