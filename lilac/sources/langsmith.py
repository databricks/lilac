"""LangSmith source."""
from typing import ClassVar, Iterable, Optional

from fastapi import APIRouter
from pydantic import Field
from typing_extensions import override

from ..env import env
from ..schema import Item
from ..source import Source, SourceSchema
from .dict_source import DictSource

router = APIRouter()

DEFAULT_LANGCHAIN_ENDPOINT = 'https://api.smith.langchain.com'


@router.get('/datasets')
def get_langsmith_datasets() -> list[str]:
  """List the datasets in LangSmith."""
  from langsmith import Client

  client = Client()
  return [d.name for d in client.list_datasets()]


class LangSmithSource(Source):
  """LangSmith data loader."""

  name: ClassVar[str] = 'langsmith'
  router: ClassVar[APIRouter] = router

  dataset_name: str = Field(description='LangSmith dataset name')

  _dict_source: Optional[DictSource] = None

  @override
  def setup(self) -> None:
    api_key = env('LANGCHAIN_API_KEY')
    api_url = env('LANGCHAIN_ENDPOINT', DEFAULT_LANGCHAIN_ENDPOINT)
    if not api_key or not api_url:
      raise ValueError(
        '`LANGCHAIN_API_KEY` and `LANGCHAIN_ENDPOINT` environment variables must be set.'
      )
    try:
      from langsmith import Client
    except ImportError:
      raise ImportError(
        'Could not import dependencies for the LangSmith source. '
        'Please install the dependency via `pip install lilac[langsmith]`.'
      )
    client = Client(api_key=api_key, api_url=api_url)

    items = [
      {**example.inputs, **(example.outputs or {})}
      for example in client.list_examples(dataset_name=self.dataset_name)
    ]

    self._dict_source = DictSource(items)
    self._dict_source.setup()

  @override
  def source_schema(self) -> SourceSchema:
    """Return the source schema."""
    assert self._dict_source is not None
    return self._dict_source.source_schema()

  @override
  def yield_items(self) -> Iterable[Item]:
    """Process the source."""
    assert self._dict_source is not None
    return self._dict_source.yield_items()
