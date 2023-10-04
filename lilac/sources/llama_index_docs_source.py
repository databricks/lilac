"""A source that reads from an Iterable of LlamaIndex Documents."""
import itertools
from typing import Any, ClassVar, Iterable, Iterator, Optional

from llama_index import Document
from typing_extensions import override

from ..schema import Item, field, infer_schema
from ..source import Source, SourceSchema

INFER_SCHEMA_SAMPLE_SIZE = 100


class LlamaIndexDocsSource(Source):
  """LlamaIndex document source

  Loads documents from a LlamaIndex Document Iterable.

  Usage:
  ```python
  from llama_index import Document, DocumentMetadata
  ```
  """ # noqa: D415, D400
  name: ClassVar[str] = 'llama_index_docs'

  _documents: Optional[Iterable[Document]]
  # Used to infer the schema.
  _infer_schema_docs: Iterator[Document]

  def __init__(self, documents: Optional[Iterable[Document]] = None, **kwargs: Any):
    super().__init__(**kwargs)
    self._documents = documents

  @override
  def source_schema(self) -> SourceSchema:
    """Return the source schema."""
    if not self._documents:
      raise ValueError('cls argument `documents` is not defined.')

    if isinstance(self._documents, list):
      num_items = len(self._documents)
    else:
      num_items = None

    preview_docs_iter, self._documents = itertools.tee(self._documents, 2)
    preview_docs = [
      doc.metadata for doc in itertools.islice(preview_docs_iter, INFER_SCHEMA_SAMPLE_SIZE)
    ]

    # Infer the schema on the first rows.
    inferred_schema = infer_schema(preview_docs)
    return SourceSchema(
      fields={
        'doc_id': field('string'),
        'text': field('string'),
        **inferred_schema.fields
      },
      num_items=num_items)

  @override
  def process(self) -> Iterable[Item]:
    """Ingest the documents."""
    if not self._documents:
      raise ValueError('cls argument `documents` is not defined.')

    for doc in self._documents:
      if not isinstance(doc, Document):
        continue
      yield {'doc_id': doc.doc_id, 'text': doc.text, **doc.metadata}
