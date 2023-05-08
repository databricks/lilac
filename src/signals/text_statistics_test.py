"""Test the semantic search signal."""

from ..schema import DataType, Field
from .text_statistics import NUM_CHARS_FEATURE_NAME, TextStatisticsSignal


def test_text_statistics_fields() -> None:
  signal = TextStatisticsSignal()
  assert signal.fields() == Field(fields={NUM_CHARS_FEATURE_NAME: Field(dtype=DataType.INT32)})


def test_text_statistics_compute() -> None:
  signal = TextStatisticsSignal()

  scores = signal.compute(['hello', 'hello world'])

  assert list(scores) == [{
    NUM_CHARS_FEATURE_NAME: len('hello')
  }, {
    NUM_CHARS_FEATURE_NAME: len('hello world')
  }]
