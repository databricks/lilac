"""Loads reddit data from Huggingface."""
from typing import ClassVar, Iterable, Optional

from pydantic import Field as PydanticField
from typing_extensions import override

from ..schema import Item
from ..source import Source, SourceSchema
from .huggingface_source import HuggingFaceSource

HF_REDDIT_DATASET_NAME = 'reddit'
HF_SUBREDDIT_COL = 'subreddit'


class RedditDataset(Source):
  """Reddit data loader, using Huggingface.

  Loads data from [huggingface.co/datasets/reddit](https://huggingface.co/datasets/reddit).
  """  # noqa: D415, D400

  name: ClassVar[str] = 'reddit'

  subreddits: Optional[list[str]] = PydanticField(
    description='If defined, only loads the subset of reddit data in these subreddit.'
  )

  _hf_dataset: HuggingFaceSource

  @override
  def setup(self) -> None:
    self._hf_dataset = HuggingFaceSource(dataset_name=HF_REDDIT_DATASET_NAME)
    self._hf_dataset.setup()

  @override
  def source_schema(self) -> SourceSchema:
    return self._hf_dataset.source_schema()

  @override
  def yield_items(self) -> Iterable[Item]:
    items = self._hf_dataset.yield_items()

    if not self.subreddits:
      return items

    lower_subreddits = [subreddit.lower() for subreddit in self.subreddits]

    for item in items:
      item_subreddit = item[HF_SUBREDDIT_COL]
      if item_subreddit.lower() not in lower_subreddits:
        # Yield None so that the progress bar is accurate.
        yield None
        continue
      yield item
