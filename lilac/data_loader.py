"""A data loader standalone binary. This should only be run as a script to load a dataset.

To run the source loader as a binary directly:

poetry run python -m lilac.data_loader \
  --dataset_name=movies_dataset \
  --output_dir=./data/ \
  --config_path=./datasets/the_movies_dataset.json
"""
import os
import pathlib
import uuid
from typing import Iterable, Optional, Union

import pandas as pd

from .data.dataset import Dataset
from .data.dataset_utils import write_items_to_parquet
from .db_manager import get_dataset
from .env import data_path
from .schema import (
  MANIFEST_FILENAME,
  PARQUET_FILENAME_PREFIX,
  UUID_COLUMN,
  Field,
  Item,
  Schema,
  SourceManifest,
  field,
  is_float,
)
from .sources.source import Source
from .tasks import TaskStepId, progress
from .utils import get_dataset_output_dir, log, open_file


def create_dataset(
  namespace: str,
  dataset_name: str,
  source_config: Source,
) -> Dataset:
  """Load a dataset from a given source configuration."""
  process_source(data_path(), namespace, dataset_name, source_config)
  return get_dataset(namespace, dataset_name)


def process_source(base_dir: Union[str, pathlib.Path],
                   namespace: str,
                   dataset_name: str,
                   source: Source,
                   task_step_id: Optional[TaskStepId] = None) -> tuple[str, int]:
  """Process a source."""
  output_dir = get_dataset_output_dir(base_dir, namespace, dataset_name)

  source.setup()
  source_schema = source.source_schema()
  items = source.process()

  # Add UUIDs and fix NaN in string columns.
  items = normalize_items(items, source_schema.fields)

  # Add progress.
  items = progress(
    items,
    task_step_id=task_step_id,
    estimated_len=source_schema.num_items,
    step_description=f'Reading from source {source.name}...')

  # Filter out the `None`s after progress.
  items = (item for item in items if item is not None)

  data_schema = Schema(fields={**source_schema.fields, UUID_COLUMN: field('string')})
  filepath, num_items = write_items_to_parquet(
    items=items,
    output_dir=output_dir,
    schema=data_schema,
    filename_prefix=PARQUET_FILENAME_PREFIX,
    shard_index=0,
    num_shards=1)

  filenames = [os.path.basename(filepath)]
  manifest = SourceManifest(files=filenames, data_schema=data_schema, images=None)
  with open_file(os.path.join(output_dir, MANIFEST_FILENAME), 'w') as f:
    f.write(manifest.json(indent=2, exclude_none=True))
  log(f'Dataset "{dataset_name}" written to {output_dir}')

  return output_dir, num_items


def normalize_items(items: Iterable[Item], fields: dict[str, Field]) -> Item:
  """Sanitize items by removing NaNs and NaTs."""
  replace_nan_fields = [
    field_name for field_name, field in fields.items() if field.dtype and not is_float(field.dtype)
  ]
  for item in items:
    if item is None:
      yield item
      continue

    # Add row uuid if it doesn't exist.
    if UUID_COLUMN not in item:
      item[UUID_COLUMN] = uuid.uuid4().hex

    # Fix NaN values.
    for field_name in replace_nan_fields:
      item_value = item.get(field_name)
      if item_value and pd.isna(item_value):
        item[field_name] = None

    yield item
