"""Convenience source method for sources that yield items row by row."""
import os
import uuid
from typing import ClassVar, Iterable, Optional

import pandas as pd
from typing_extensions import override

from ..data.dataset_utils import write_items_to_parquet
from ..schema import (
  PARQUET_FILENAME_PREFIX,
  ROWID,
  Field,
  Item,
  Schema,
  is_float,
)
from ..source import Source, SourceManifest
from ..tasks import TaskStepId, progress


class ItemSource(Source):
  """A managed class allowing users to define their source as an Iterable[Item]."""

  name: ClassVar[str] = 'item'

  def yield_items(self) -> Iterable[Item]:
    """Process the source, yielding an iterable of items."""
    raise NotImplementedError

  @override
  def process(self, output_dir: str, task_step_id: Optional[TaskStepId] = None) -> SourceManifest:
    source_schema = self.source_schema()
    items = self.yield_items()

    # Add rowids and fix NaN in string columns.
    items = normalize_items(items, source_schema.fields)

    # Add progress.
    items = progress(
      items,
      task_step_id=task_step_id,
      estimated_len=source_schema.num_items,
      step_description=f'Reading from source {self.name}...',
    )

    # Filter out the `None`s after progress.
    items = (item for item in items if item is not None)

    data_schema = Schema(fields=source_schema.fields.copy())
    filepath = write_items_to_parquet(
      items=items,
      output_dir=output_dir,
      schema=data_schema,
      filename_prefix=PARQUET_FILENAME_PREFIX,
      shard_index=0,
      num_shards=1,
    )

    filenames = [os.path.basename(filepath)]
    manifest = SourceManifest(files=filenames, data_schema=data_schema, images=None, source=self)
    return manifest


def normalize_items(items: Iterable[Item], fields: dict[str, Field]) -> Item:
  """Sanitize items by removing NaNs and NaTs."""
  replace_nan_fields = [
    field_name for field_name, field in fields.items() if field.dtype and not is_float(field.dtype)
  ]
  for item in items:
    if item is None:
      yield item
      continue

    # Add rowid if it doesn't exist.
    if ROWID not in item:
      item[ROWID] = uuid.uuid4().hex

    # Fix NaN values.
    for field_name in replace_nan_fields:
      item_value = item.get(field_name)
      if item_value and not isinstance(item_value, Iterable) and pd.isna(item_value):
        item[field_name] = None

    yield item
