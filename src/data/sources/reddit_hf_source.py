"""Loads reddit data from Huggingface."""
from typing import Iterable, Optional

from pydantic import Field as PydanticField
from typing_extensions import override

from ...schema import Item
from .huggingface_source import HuggingFaceDataset
from .source import Source, SourceSchema

HF_REDDIT_DATASET_NAME = 'reddit'
HF_SUBREDDIT_COL = 'subreddit'


class RedditDataset(Source):
  """Reddit data loader, using Huggingface.

  Loads data from [huggingface.co/datasets/reddit](https://huggingface.co/datasets/reddit).
  """ # noqa: D415, D400
  name = 'reddit'

  subreddits: Optional[list[str]] = PydanticField(
    required=False,
    description='If defined, only loads the subset of reddit data in these subreddit.',
  )

  _hf_dataset: HuggingFaceDataset

  @override
  def prepare(self) -> None:
    self._hf_dataset = HuggingFaceDataset(dataset_name=HF_REDDIT_DATASET_NAME)
    self._hf_dataset.prepare()

  @override
  def source_schema(self) -> SourceSchema:
    return self._hf_dataset.source_schema()

  @override
  def process(self) -> Iterable[Item]:
    items = self._hf_dataset.process()

    if not self.subreddits:
      return items

    for item in items:
      item_subreddit = item[HF_SUBREDDIT_COL]
      if item_subreddit.lower() not in self.subreddits:
        # Yield None so that the progress bar is accurate.
        yield None
        continue
      yield item
