"""Test the Substring Search signal."""

import pytest

from ..schema import field
from .splitters.text_splitter_test_utils import text_to_expected_spans
from .substring_search import SubstringSignal


def test_substring_fields() -> None:
  signal = SubstringSignal(query='test')
  assert signal.fields() == field(['string_span'])


def test_query_is_required() -> None:
  with pytest.raises(TypeError):
    SubstringSignal()  # type: ignore


def test_compute() -> None:
  signal = SubstringSignal(query='test')

  text = 'The word TEST shows up 3 times, teST and test'
  spans = list(signal.compute([text]))

  expected_spans = text_to_expected_spans(text, ['TEST', 'teST', 'test'])
  assert [expected_spans] == spans
