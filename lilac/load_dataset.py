"""A data loader standalone binary. This should only be run as a script to load a dataset.

To run the source loader as a binary directly:

poetry run python -m lilac.load_dataset \
  --dataset_name=movies_dataset \
  --output_dir=./data/ \
  --config_path=./datasets/the_movies_dataset.json
"""
import os
import pathlib
import uuid
from typing import Iterable, Optional, Union

import pandas as pd

from .config import DatasetConfig
from .data.dataset import Dataset, default_settings
from .data.dataset_utils import write_items_to_parquet
from .db_manager import get_dataset
from .env import get_project_dir
from .project import add_project_dataset_config, update_project_dataset_settings
from .schema import MANIFEST_FILENAME, PARQUET_FILENAME_PREFIX, ROWID, Field, Item, Schema, is_float
from .source import Source, SourceManifest
from .tasks import TaskStepId, progress
from .utils import get_dataset_output_dir, log, open_file


def create_dataset(
  config: DatasetConfig,
  project_dir: Optional[Union[str, pathlib.Path]] = None,
  overwrite: bool = False,
) -> Dataset:
  """Load a dataset from a given source configuration.

  Args:
    config: The dataset configuration to load.
    project_dir: The path to the project directory for where to create the dataset. If not defined,
      uses the project directory from `LILAC_PROJECT_DIR` or [deprecated] `LILAC_DATA_PATH`.
    overwrite: Whether to overwrite the dataset if it already exists.
  """
  project_dir = project_dir or get_project_dir()
  if not project_dir:
    raise ValueError(
      '`project_dir` must be defined. Please pass a `project_dir` or set it '
      'globally with `set_project_dir(path)`'
    )

  # Update the config before processing the source.
  add_project_dataset_config(config, project_dir, overwrite)

  process_source(project_dir, config)
  return get_dataset(config.namespace, config.name, project_dir)


def process_source(
  project_dir: Union[str, pathlib.Path],
  config: DatasetConfig,
  task_step_id: Optional[TaskStepId] = None,
) -> str:
  """Process a source."""
  output_dir = get_dataset_output_dir(project_dir, config.namespace, config.name)

  config.source.setup()
  try:
    manifest = config.source.load_to_parquet(output_dir, task_step_id=task_step_id)
  except NotImplementedError:
    manifest = slow_process(config.source, output_dir, task_step_id=task_step_id)

  with open_file(os.path.join(output_dir, MANIFEST_FILENAME), 'w') as f:
    f.write(manifest.model_dump_json(indent=2, exclude_none=True))

  if not config.settings:
    dataset = get_dataset(config.namespace, config.name, project_dir)
    settings = default_settings(dataset)
    update_project_dataset_settings(config.namespace, config.name, settings, project_dir)

  log(f'Dataset "{config.name}" written to {output_dir}')

  return output_dir


def slow_process(
  source: Source, output_dir: str, task_step_id: Optional[TaskStepId] = None
) -> SourceManifest:
  """Process the items of a source, writing to parquet.

  Args:
    source: The source to process.
    output_dir: The directory to write the parquet files to.
    task_step_id: The TaskManager `task_step_id` for this process run. This is used to update the
      progress of the task.

  Returns:
    A SourceManifest that describes schema and parquet file locations.
  """
  source_schema = source.source_schema()
  items = source.yield_items()

  # Add rowids and fix NaN in string columns.
  items = normalize_items(items, source_schema.fields)

  # Add progress.
  items = progress(
    items,
    task_step_id=task_step_id,
    estimated_len=source_schema.num_items,
    step_description=f'Reading from source {source.name}...',
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
  manifest = SourceManifest(files=filenames, data_schema=data_schema, images=None, source=source)
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
