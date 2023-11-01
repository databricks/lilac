"""Tests for the language detection signal."""

from pytest_mock import MockerFixture

from ..schema import lilac_span
from . import lang_detection
from .lang_detection import LANG_CODE, LangDetectionSignal


def test_lang_detection_sentences(mocker: MockerFixture) -> None:
  signal = LangDetectionSignal()
  mocker.patch(f'{lang_detection.__name__}.TEXT_LEN_THRESHOLD', 1)
  signal.setup()
  docs = ['War doesnt show whos right, just whos left.', 'Ein, zwei, drei, vier']
  res = list(signal.compute(docs))
  assert res == ['en', 'de']


def test_lang_detection_multiple_paragraphs(mocker: MockerFixture) -> None:
  signal = LangDetectionSignal(split_by_paragraph=True)
  mocker.patch(f'{lang_detection.__name__}.TEXT_LEN_THRESHOLD', 1)
  signal.setup()
  doc = 'War doesnt show whos right, just whos left.\n\nEin, zwei, drei, vier'
  res = list(signal.compute([doc]))
  assert res == [[lilac_span(0, 43, {LANG_CODE: 'en'}), lilac_span(45, 66, {LANG_CODE: 'de'})]]


def test_text_too_short(mocker: MockerFixture) -> None:
  signal = LangDetectionSignal()
  mocker.patch(f'{lang_detection.__name__}.TEXT_LEN_THRESHOLD', 25)
  signal.setup()
  docs = ['War doesnt show whos right, just whos left.', 'Ein, zwei, drei, vier']
  res = list(signal.compute(docs))
  assert res == ['en', 'TOO_SHORT']
