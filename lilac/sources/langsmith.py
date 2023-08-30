"""LangSmith source."""
from typing import Iterable, Optional

import pandas as pd
from fastapi import APIRouter
from pydantic import Field
from typing_extensions import override

from ..schema import Item
from .source import Source, SourceSchema, schema_from_df

LINE_NUMBER_COLUMN = '__line_number__'

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
  _df: Optional[pd.DataFrame] = None

  @override
  def setup(self) -> None:
    try:
      from langsmith import Client
    except ImportError:
      raise ImportError('Could not import dependencies for the LangSmith source. '
                        'Please install the optional dependency via `pip install langsmith`.')
    client = Client()

    self._df = pd.DataFrame([{
      **example.inputs,
      **example.outputs
    } for example in client.list_examples(dataset_name=self.dataset_name)])

    # Create the source schema in prepare to share it between process and source_schema.
    self._source_schema = schema_from_df(self._df, LINE_NUMBER_COLUMN)

  @override
  def source_schema(self) -> SourceSchema:
    """Return the source schema."""
    assert self._source_schema is not None
    return self._source_schema

  @override
  def process(self) -> Iterable[Item]:
    """Process the source upload request."""
    if self._df is None:
      raise RuntimeError('The langsmith source is not initialized.')

    cols = self._df.columns.tolist()
    yield from ({
      LINE_NUMBER_COLUMN: idx,
      **dict(zip(cols, item_vals)),
    } for idx, *item_vals in self._df.itertuples())
