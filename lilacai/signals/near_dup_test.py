"""Test the Near duplicate signal."""

from .near_dup import CLUSTER_KEY, NearDuplicateSignal


def test_exact_duplicates() -> None:
  signal = NearDuplicateSignal()
  docs = ['Hello', 'Everyone', 'Hello', 'Hi']
  assert list(signal.compute(docs)) == [{CLUSTER_KEY: x} for x in [0, 1, 0, 3]]


def test_near_dups() -> None:
  signal = NearDuplicateSignal()
  docs = [
    'Hello everyone. This is a test for near duplication with almost the same content',
    'Hello everyone. This is a test for near duplication with almost the same content [time]',
  ]
  assert list(signal.compute(docs)) == [{CLUSTER_KEY: x} for x in [0, 0]]
