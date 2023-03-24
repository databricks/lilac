"""Text splitters using spaCy."""
from spacy import Language
from typing_extensions import override  # type: ignore

from .spacy_utils import load_spacy
from .text_splitter import TextSpan, TextSplitter


class SentenceSplitterSpacy(TextSplitter):
  """Splits documents into sentences."""
  name = 'sentences_spacy'

  pipeline: str

  _tokenizer: Language

  def __init__(self, pipeline: str = 'en_core_web_sm'):
    super().__init__(pipeline=pipeline)
    self._tokenizer = load_spacy(pipeline)

  @override
  def split(self, text: str) -> list[TextSpan]:
    sentences = self._tokenizer(text).sents
    return [TextSpan(start=token.start_char, end=token.end_char) for token in sentences]
