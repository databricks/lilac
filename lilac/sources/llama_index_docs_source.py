"""A source that reads from an Iterable of LlamaIndex Documents."""
from typing import TYPE_CHECKING, Any, ClassVar, Iterable, Iterator, Optional

if TYPE_CHECKING:
  from llama_index import Document

from typing_extensions import override

from ..schema import Item
from ..source import Source, SourceSchema
from .dict_source import DictSource


class LlamaIndexDocsSource(Source):
  """LlamaIndex document source

  Loads documents from a LlamaIndex Document Iterable.

  Usage:
  ```python
    from llama_index import download_loader

    # See: https://llamahub.ai/l/papers-arxiv
    ArxivReader = download_loader("ArxivReader")

    loader = ArxivReader()
    documents = loader.load_data(search_query='au:Karpathy')

    # Create the dataset
    ll.create_dataset(
    config=ll.DatasetConfig(
      namespace='local',
      name='arxiv-karpathy',
      source=ll.LlamaIndexDocsSource(
        # documents comes from the loader.load_data call in the previous cell.
        documents=documents
        )
      )
    )
  ```

  A detailed example notebook
  [can be found here](https://github.com/lilacai/lilac/blob/main/notebooks/LlamaIndexLoader.ipynb)
  """  # noqa: D415, D400

  name: ClassVar[str] = 'llama_index_docs'

  _documents: Optional[Iterable['Document']]
  # Used to infer the schema.
  _infer_schema_docs: Iterator['Document']

  _dict_source: Optional[DictSource] = None

  def __init__(self, documents: Optional[Iterable['Document']] = None, **kwargs: Any):
    super().__init__(**kwargs)
    self._documents = documents

  @override
  def setup(self) -> None:
    """Setup the source."""
    if not self._documents:
      raise ValueError('cls argument `documents` is not defined.')

    self._dict_source = DictSource(self._get_doc_items())
    self._dict_source.setup()

  def _get_doc_items(self) -> Iterable[Item]:
    if not self._documents:
      raise ValueError('cls argument `documents` is not defined.')

    for doc in self._documents:
      yield {'doc_id': str(doc.doc_id), 'text': doc.text, **doc.metadata}

  @override
  def source_schema(self) -> SourceSchema:
    """Return the source schema."""
    if not self._dict_source:
      raise ValueError('Please call setup() before calling `source_schema`.')

    return self._dict_source.source_schema()

  @override
  def yield_items(self) -> Iterable[Item]:
    """Ingest the documents."""
    if not self._dict_source:
      raise ValueError('Please call setup() before calling `process`.')

    return self._dict_source.yield_items()
