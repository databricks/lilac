"""LangSmith source."""
from typing import Iterable, Optional

from fastapi import APIRouter
from pydantic import Field
from typing_extensions import override

from ..schema import Item, infer_schema
from .source import Source, SourceSchema

router = APIRouter()


@router.get('/datasets')
def get_datasets() -> list[str]:
  """List the datasets in LangSmith."""
  from langsmith import Client
  client = Client()
  return [d.name for d in client.list_datasets()]


class LangSmithSource(Source):
  """LangSmith data loader."""
  name = 'langsmith'
  router = router

  dataset_name: str = Field(description='The LangSmith dataset name')

  _source_schema: Optional[SourceSchema] = None
  _items: Optional[Item] = None

  @override
  def setup(self) -> None:
    try:
      from langsmith import Client
    except ImportError:
      raise ImportError('Could not import dependencies for the LangSmith source. '
                        'Please install the optional dependency via `pip install langsmith`.')
    client = Client()

    self._items = [{
      **example.inputs,
      **example.outputs
    } for example in client.list_examples(dataset_name=self.dataset_name)]

    # Create the source schema in prepare to share it between process and source_schema.
    schema = infer_schema(self._items)
    self._source_schema = SourceSchema(fields=schema.fields, num_items=len(self._items))

  @override
  def source_schema(self) -> SourceSchema:
    """Return the source schema."""
    assert self._source_schema is not None
    return self._source_schema

  @override
  def process(self) -> Iterable[Item]:
    """Process the source upload request."""
    if self._items is None:
      raise RuntimeError('The langsmith source is not initialized.')

    yield from self._items
