"""Tests the vector store interface."""

import pathlib
from typing import Type

import numpy as np
import pytest

from .vector_store import VectorStore
from .vector_store_numpy import NumpyVectorStore

ALL_STORES = [NumpyVectorStore]


@pytest.mark.parametrize('store_cls', ALL_STORES)
class VectorStoreSuite:

  def test_get_all(self, tmp_path: pathlib.Path, store_cls: Type[VectorStore]) -> None:
    store = store_cls()

    store.add(['a', 'b', 'c'], np.array([[1, 2, 3], [4, 5, 6], [7, 8, 9]]))

    np.testing.assert_array_equal(store.get(['a', 'b', 'c']),
                                  np.array([[1, 2, 3], [4, 5, 6], [7, 8, 9]]))

  def test_get_subset(self, tmp_path: pathlib.Path, store_cls: Type[VectorStore]) -> None:
    store = store_cls()

    store.add(['a', 'b', 'c'], np.array([[1, 2, 3], [4, 5, 6], [7, 8, 9]]))

    np.testing.assert_array_equal(store.get(['b', 'c']), np.array([[4, 5, 6], [7, 8, 9]]))
