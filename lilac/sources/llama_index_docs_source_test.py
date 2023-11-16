"""Tests for the Llama Index Docs source."""

from llama_index import Document

from ..schema import schema
from ..source import SourceSchema
from .llama_index_docs_source import LlamaIndexDocsSource


def test_simple_llama_index_documents() -> None:
  docs = [
    Document(doc_id='id_1', text='test', extra_info={'name': 'a', 'age': 1}),
    Document(doc_id='id_2', text='test2', extra_info={'name': 'b', 'age': 2}),
    Document(doc_id='id_3', text='test3', extra_info={'name': 'c', 'age': 3}),
  ]

  source = LlamaIndexDocsSource(docs)
  source.setup()

  source_schema = source.source_schema()
  assert source_schema == SourceSchema(
    fields=schema({'doc_id': 'string', 'text': 'string', 'name': 'string', 'age': 'int64'}).fields,
    num_items=3,
  )

  items = list(source.yield_items())

  assert items == [
    {'doc_id': 'id_1', 'text': 'test', 'name': 'a', 'age': 1},
    {'doc_id': 'id_2', 'text': 'test2', 'name': 'b', 'age': 2},
    {'doc_id': 'id_3', 'text': 'test3', 'name': 'c', 'age': 3},
  ]
