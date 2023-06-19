"""A data loader standalone binary. This should only be run as a script to load a dataset.

To run the source loader as a binary directly:

poetry run python -m src.data_loader \
  --dataset_name=movies_dataset \
  --output_dir=./data/ \
  --config_path=./datasets/the_movies_dataset.json
"""
import json
import math
import os
import pathlib
import uuid
from typing import Iterable, Optional, Union, cast

import click
import pandas as pd
from distributed import Client

from .data.dataset_utils import write_items_to_parquet
from .data.sources.default_sources import register_default_sources
from .data.sources.source import Source
from .data.sources.source_registry import resolve_source
from .schema import (
  MANIFEST_FILENAME,
  PARQUET_FILENAME_PREFIX,
  UUID_COLUMN,
  DataType,
  Field,
  Item,
  Schema,
  SourceManifest,
  field,
)
from .tasks import TaskStepId, progress
from .utils import get_dataset_output_dir, log, open_file


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
  if task_step_id is not None:
    items = progress(
      items,
      task_step_id=task_step_id,
      estimated_len=source_schema.num_items,
      step_description=f'Reading from source {source.name}...')

  # Filter out the `None`s after progress.
  items = cast(Iterable[Item], (item for item in items if item is not None))

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
  log(f'Manifest for dataset "{dataset_name}" written to {output_dir}')

  return output_dir, num_items


def normalize_items(items: Iterable[Item], fields: dict[str, Field]) -> Item:
  """Sanitize items by removing NaNs and NaTs."""
  string_fields = set(
    [field_name for field_name, field in fields.items() if field.dtype == DataType.STRING])
  timestamp_fields = set(
    [field_name for field_name, field in fields.items() if field.dtype == DataType.TIMESTAMP])
  for item in items:
    if item is None:
      yield item
      continue

    # Add row uuid if it doesn't exist.
    if UUID_COLUMN not in item:
      item[UUID_COLUMN] = uuid.uuid4().hex

    # Fix NaN string fields.
    for name in string_fields:
      item_value = item.get(name)
      if item_value and not isinstance(item_value, str):
        if math.isnan(item_value):
          item[name] = None
        else:
          item[name] = str(item_value)

    # Fix NaT (not a time) timestamp fields.
    for name in timestamp_fields:
      item_value = item.get(name)
      if item_value and pd.isnull(item_value):
        item[name] = None

    yield item


@click.command()
@click.option(
  '--output_dir',
  required=True,
  type=str,
  help='The output directory to write the parquet files to.')
@click.option(
  '--config_path',
  required=True,
  type=str,
  help='The path to a json file describing the source configuration.')
@click.option(
  '--dataset_name', required=True, type=str, help='The dataset name, used for binary mode only.')
@click.option(
  '--namespace',
  required=False,
  default='local',
  type=str,
  help='The namespace to use. Defaults to "local".')
def main(output_dir: str, config_path: str, dataset_name: str, namespace: str) -> None:
  """Run the source loader as a binary."""
  register_default_sources()

  with open_file(config_path) as f:
    # Parse the json file in a dict.
    source_dict = json.load(f)
    source = resolve_source(source_dict)

  client = Client()
  client.submit(process_source, output_dir, namespace, dataset_name, source).result()


if __name__ == '__main__':
  main()
