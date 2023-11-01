"""Tests for concept."""

from .concept import DRAFT_MAIN, Concept, ConceptType, Example, draft_examples


def test_draft_examples_main() -> None:
  concept = Concept(
    namespace='test_namespace',
    concept_name='test_name',
    type=ConceptType.TEXT,
    data={
      '0': Example(id='0', label=True, text='hello'),
      '1': Example(id='1', label=False, text='world'),
    },
    version=0,
  )

  assert draft_examples(concept, DRAFT_MAIN) == {
    '0': Example(id='0', label=True, text='hello'),
    '1': Example(id='1', label=False, text='world'),
  }


def test_draft_examples_simple_draft() -> None:
  concept = Concept(
    namespace='test_namespace',
    concept_name='test_name',
    type=ConceptType.TEXT,
    data={
      '0': Example(id='0', label=True, text='hello'),
      '1': Example(id='1', label=False, text='world'),
      '2': Example(id='2', label=True, text='hello draft 1', draft='draft1'),
      '3': Example(id='3', label=False, text='world draft 1', draft='draft1'),
      '4': Example(id='4', label=True, text='hello draft 2', draft='draft2'),
      '5': Example(id='5', label=False, text='world draft 2', draft='draft2'),
    },
    version=0,
  )

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
    type=ConceptType.TEXT,
    data={
      '0': Example(id='0', label=True, text='hello'),
      '1': Example(id='1', label=False, text='world'),
      # Duplicate text.
      '2': Example(id='2', label=False, text='hello', draft='draft'),
      '3': Example(id='3', label=False, text='world draft', draft='draft'),
    },
    version=0,
  )

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
