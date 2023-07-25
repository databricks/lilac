"""Test the semantic search signal."""

from typing import cast

from pytest import approx

from ..schema import DataType, Field
from .text_statistics import NUM_CHARS, READABILITY, TYPE_TOKEN_RATIO, TextStatisticsSignal


def test_text_statistics_fields() -> None:
  signal = TextStatisticsSignal()
  signal.setup()
  assert signal.fields() == Field(
    fields={
      NUM_CHARS: Field(dtype=DataType.INT32),
      READABILITY: Field(dtype=DataType.FLOAT32),
      TYPE_TOKEN_RATIO: Field(dtype=DataType.FLOAT32)
    })


def test_text_statistics_compute() -> None:
  signal = TextStatisticsSignal()
  signal.setup()

  scores = signal.compute(['hello', 'hello world'])
  assert list(scores) == [{
    NUM_CHARS: 5,
    READABILITY: approx(2.62),
    TYPE_TOKEN_RATIO: 0.0
  }, {
    NUM_CHARS: 10,
    READABILITY: approx(3.12),
    TYPE_TOKEN_RATIO: 1.0
  }]


def test_text_statistics_missing_value() -> None:
  signal = TextStatisticsSignal()
  signal.setup()

  scores = signal.compute(['hello', cast(str, None), 'everybody'])

  assert list(scores) == [{
    NUM_CHARS: 5,
    READABILITY: approx(2.62),
    TYPE_TOKEN_RATIO: 0.0
  }, None, {
    NUM_CHARS: 9,
    READABILITY: approx(21.46),
    TYPE_TOKEN_RATIO: 0.0
  }]
