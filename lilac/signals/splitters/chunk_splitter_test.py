"""Tests the chunk splitter."""

from .chunk_splitter import ChunkSplitter
from .text_splitter_test_utils import spans_to_text, text_to_expected_spans


def test_paragraphs_no_overlap() -> None:
  signal = ChunkSplitter(chunk_size=12, chunk_overlap=0)
  text = 'Hello.\n\nThis will get split.\n\nThe sentence\n\nA.\n\nB.\n\nC.'
  split_items = list(signal.compute([text]))

  # "This will get split" should split in 2 chunks, and "A.\n\nB.\n\nC." should be 1 chunk.
  expected_spans = text_to_expected_spans(
    text, ['Hello.', 'This will', 'get split.', 'The sentence', 'A.\n\nB.\n\nC.'])
  assert split_items == [expected_spans]


def test_single_world_is_too_long_no_overlap() -> None:
  signal = ChunkSplitter(chunk_size=6, chunk_overlap=0)
  text = 'ThisIsASingleWordThatIsTooLong'
  split_items = list(signal.compute([text]))

  expected_spans = text_to_expected_spans(text, ['ThisIs', 'ASingl', 'eWordT', 'hatIsT', 'ooLong'])
  assert split_items == [expected_spans]


def test_newlines_with_overlap() -> None:
  signal = ChunkSplitter(chunk_size=12, chunk_overlap=5)
  text = 'Hello.\n\nWorld.\n\nThis will get split.'
  spans = list(signal.compute([text]))[0]

  expected_chunks = ['Hello.', 'World.', 'This will', 'will get', 'get split.']
  assert spans_to_text(text, spans) == expected_chunks


def test_serialization() -> None:
  signal = ChunkSplitter(chunk_size=12, chunk_overlap=5)
  assert signal.dict() == {
    'signal_name': 'chunk',
    'chunk_size': 12,
    'chunk_overlap': 5,
    'separators': ['```', '\n\n', '\n', ' ', '']
  }


def test_split_code() -> None:
  signal = ChunkSplitter(chunk_size=60, chunk_overlap=0)
  text = """
    We expected the entire code to be one span.

    ```python
    def hello():
      echo('hello')
    ```

    This is the rest of the text.
  """
  spans = list(signal.compute([text]))[0]
  expected_chunks = [
    """
    We expected the entire code to be one span.

    """,
    """```python
    def hello():
      echo('hello')
    ```""",
    """

    This is the rest of the text.
  """,
  ]
  assert spans_to_text(text, spans) == expected_chunks
