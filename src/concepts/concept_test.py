"""Tests for concept."""

from ..schema import SignalInputType
from .concept import DRAFT_MAIN, Concept, Example, draft_examples


def test_draft_examples_main() -> None:
  concept = Concept(
    namespace='test_namespace',
    concept_name='test_name',
    type=SignalInputType.TEXT,
    data={
      '0': Example(id='0', label=True, text='hello'),
      '1': Example(id='1', label=False, text='world'),
    },
    version=0)

  assert draft_examples(concept, DRAFT_MAIN) == {
    '0': Example(id='0', label=True, text='hello'),
    '1': Example(id='1', label=False, text='world'),
  }


def test_draft_examples_simple_draft() -> None:
  concept = Concept(
    namespace='test_namespace',
    concept_name='test_name',
    type=SignalInputType.TEXT,
    data={
      '0': Example(id='0', label=True, text='hello'),
      '1': Example(id='1', label=False, text='world'),
      '2': Example(id='2', label=True, text='hello draft 1', draft='draft1'),
      '3': Example(id='3', label=False, text='world draft 1', draft='draft1'),
      '4': Example(id='4', label=True, text='hello draft 2', draft='draft2'),
      '5': Example(id='5', label=False, text='world draft 2', draft='draft2'),
    },
    version=0)

  assert draft_examples(concept, DRAFT_MAIN) == {
    '0': Example(id='0', label=True, text='hello'),
    '1': Example(id='1', label=False, text='world'),
  }

  assert draft_examples(concept, 'draft1') == {
    '0': Example(id='0', label=True, text='hello'),
    '1': Example(id='1', label=False, text='world'),
    '2': Example(id='2', label=True, text='hello draft 1', draft='draft1'),
    '3': Example(id='3', label=False, text='world draft 1', draft='draft1'),
  }

  assert draft_examples(concept, 'draft2') == {
    '0': Example(id='0', label=True, text='hello'),
    '1': Example(id='1', label=False, text='world'),
    '4': Example(id='4', label=True, text='hello draft 2', draft='draft2'),
    '5': Example(id='5', label=False, text='world draft 2', draft='draft2'),
  }


def test_draft_examples_draft_dedupe() -> None:
  concept = Concept(
    namespace='test_namespace',
    concept_name='test_name',
    type=SignalInputType.TEXT,
    data={
      '0': Example(id='0', label=True, text='hello'),
      '1': Example(id='1', label=False, text='world'),
      # Duplicate text.
      '2': Example(id='2', label=False, text='hello', draft='draft'),
      '3': Example(id='3', label=False, text='world draft', draft='draft'),
    },
    version=0)

  assert draft_examples(concept, DRAFT_MAIN) == {
    '0': Example(id='0', label=True, text='hello'),
    '1': Example(id='1', label=False, text='world'),
  }

  assert draft_examples(concept, 'draft') == {
    # 0 is deduplicated with 2.
    '1': Example(id='1', label=False, text='world'),
    # 2 overrides 0's label.
    '2': Example(id='2', label=False, text='hello', draft='draft'),
    '3': Example(id='3', label=False, text='world draft', draft='draft'),
  }


def test_merge_draft() -> None:
  concept = Concept(
    namespace='test_namespace',
    concept_name='test_name',
    type=SignalInputType.TEXT,
    data={
      '0': Example(id='0', label=True, text='hello'),
      '1': Example(id='1', label=False, text='world'),
      '2': Example(id='2', label=True, text='hello draft 1', draft='draft1'),
      '3': Example(id='3', label=False, text='world draft 1', draft='draft1'),
      '4': Example(id='4', label=True, text='hello draft 2', draft='draft2'),
      '5': Example(id='5', label=False, text='world draft 2', draft='draft2'),
    },
    version=0)

  concept.merge_draft('draft1')

  assert concept == Concept(
    namespace='test_namespace',
    concept_name='test_name',
    type=SignalInputType.TEXT,
    data={
      '0': Example(id='0', label=True, text='hello'),
      '1': Example(id='1', label=False, text='world'),
      # Draft examples are merged.
      '2': Example(id='2', label=True, text='hello draft 1'),
      '3': Example(id='3', label=False, text='world draft 1'),
      # Draft 2 is untouched.
      '4': Example(id='4', label=True, text='hello draft 2', draft='draft2'),
      '5': Example(id='5', label=False, text='world draft 2', draft='draft2'),
    },
    version=1)

  concept.merge_draft('draft2')

  assert concept == Concept(
    namespace='test_namespace',
    concept_name='test_name',
    type=SignalInputType.TEXT,
    data={
      '0': Example(id='0', label=True, text='hello'),
      '1': Example(id='1', label=False, text='world'),
      # Draft examples are merged.
      '2': Example(id='2', label=True, text='hello draft 1'),
      '3': Example(id='3', label=False, text='world draft 1'),
      # Draft 2 examples are merged.
      '4': Example(id='4', label=True, text='hello draft 2'),
      '5': Example(id='5', label=False, text='world draft 2'),
    },
    version=2)


def test_merge_draft_dedupe() -> None:
  concept = Concept(
    namespace='test_namespace',
    concept_name='test_name',
    type=SignalInputType.TEXT,
    data={
      '0': Example(id='0', label=True, text='hello'),
      '1': Example(id='1', label=False, text='world'),
      # Labels are switched in draft1.
      '2': Example(id='2', label=False, text='hello', draft='draft1'),
      '3': Example(id='3', label=True, text='world', draft='draft1'),
      # Labels are the same in draft2.
      '4': Example(id='4', label=True, text='hello', draft='draft2'),
      '5': Example(id='5', label=False, text='world', draft='draft2'),
    },
    version=0)

  concept.merge_draft('draft1')

  assert concept == Concept(
    namespace='test_namespace',
    concept_name='test_name',
    type=SignalInputType.TEXT,
    data={
      # Main is overwritten by draft as they are duplicates.
      '2': Example(id='2', label=False, text='hello'),
      '3': Example(id='3', label=True, text='world'),
      # Draft 2 is untouched.
      '4': Example(id='4', label=True, text='hello', draft='draft2'),
      '5': Example(id='5', label=False, text='world', draft='draft2'),
    },
    version=1)

  concept.merge_draft('draft2')

  assert concept == Concept(
    namespace='test_namespace',
    concept_name='test_name',
    type=SignalInputType.TEXT,
    data={
      # Main is overwritten by draft2 again as they are duplicates.
      '4': Example(id='4', label=True, text='hello'),
      '5': Example(id='5', label=False, text='world'),
    },
    version=2)
