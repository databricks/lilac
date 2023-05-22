"""Loads reddit data from Huggingface."""
import multiprocessing
from typing import Iterable, Optional, Union, cast

import tensorflow as tf
from pydantic import BaseModel
from pydantic import Field as PydanticField
from typing_extensions import override

# mypy: disable-error-code="attr-defined"
from datasets import DatasetDict, load_dataset

from ...schema import PARQUET_FILENAME_PREFIX, Item, Schema
from ...tasks import TaskId, progress
from ..dataset_utils import write_items_to_parquet
from .huggingface_source import hf_schema_to_schema
from .source import Source, SourceProcessResult

TFDSElement = Union[dict, tf.RaggedTensor, tf.Tensor]

HF_SPLIT_COLUMN = '__hfsplit__'
HF_REDDIT_DATASET_NAME = 'reddit'
HF_SUBREDDIT_COL = 'subreddit'

# Used when the dataset is saved locally.
DEFAULT_LOCAL_SPLIT_NAME = 'default'


class SchemaInfo(BaseModel):
  """Information about the processed huggingface schema."""
  data_schema: Schema
  class_labels: dict[str, list[str]]
  num_items: int


def _convert_to_items(hf_dataset_dict: DatasetDict, subreddits: Optional[list[str]],
                      class_labels: dict[str, list[str]]) -> Iterable[Optional[Item]]:
  """Convert a huggingface split datasets to an iterable of items."""
  split_names = list(hf_dataset_dict.keys())
  subreddits = [s.lower() for s in subreddits or []]

  for split_name in split_names:
    split_dataset = hf_dataset_dict[split_name]
    for example in split_dataset:
      # Replace the class labels with strings.
      for feature_name in class_labels.keys():
        if feature_name in example:
          example[feature_name] = class_labels[feature_name][example[feature_name]]

      # Inject the split name.
      example[HF_SPLIT_COLUMN] = split_name

      # Filter out anything that isn't in the requested subreddits.
      if subreddits:
        item_subreddit = example[HF_SUBREDDIT_COL]
        if item_subreddit.lower() not in subreddits:
          # Yield None so that the progress bar is accurate.
          yield None
          continue

      yield example


class RedditDataset(Source):
  """Reddit data loader, using Huggingface.

  Loads data from [huggingface.co/datasets/reddit](https://huggingface.co/datasets/reddit).
  """ # noqa: D415, D400
  name = 'reddit'

  subreddits: Optional[list[str]] = PydanticField(
    required=False,
    description='If defined, only loads the subset of reddit data in these subreddit.',
  )

  @override
  def process(
    self,
    output_dir: str,
    task_id: Optional[TaskId] = None,
  ) -> SourceProcessResult:
    hf_dataset_dict = load_dataset(HF_REDDIT_DATASET_NAME, num_proc=multiprocessing.cpu_count())

    schema_info = hf_schema_to_schema(hf_dataset_dict, split=None)

    # Items will include a bunch of `None`s so that the progress estimate is accurate.
    items = progress(
      _convert_to_items(hf_dataset_dict, self.subreddits, schema_info.class_labels),
      task_id=task_id,
      estimated_len=schema_info.num_items)

    # Filter out the `None`s.
    items = cast(Iterable[Item], (item for item in items if item is not None))

    filepath, num_items = write_items_to_parquet(
      items=items,
      output_dir=output_dir,
      schema=schema_info.data_schema,
      filename_prefix=PARQUET_FILENAME_PREFIX,
      shard_index=0,
      num_shards=1)

    return SourceProcessResult(
      filepaths=[filepath], data_schema=schema_info.data_schema, images=None, num_items=num_items)
