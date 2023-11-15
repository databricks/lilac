"""A data loader standalone binary. This should only be run as a script to load a dataset.

To run the source loader as a binary directly:

poetry run python -m lilac.load_dataset \
  --dataset_name=movies_dataset \
  --output_dir=./data/ \
  --config_path=./datasets/the_movies_dataset.json
"""
import os
import pathlib
from typing import Optional, Union

from .config import DatasetConfig
from .data.dataset import Dataset, default_settings
from .db_manager import get_dataset
from .env import get_project_dir
from .project import add_project_dataset_config, update_project_dataset_settings
from .schema import MANIFEST_FILENAME
from .tasks import TaskStepId
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
  manifest = config.source.process(output_dir, task_step_id=task_step_id)

  with open_file(os.path.join(output_dir, MANIFEST_FILENAME), 'w') as f:
    f.write(manifest.model_dump_json(indent=2, exclude_none=True))

  if not config.settings:
    dataset = get_dataset(config.namespace, config.name, project_dir)
    settings = default_settings(dataset)
    update_project_dataset_settings(config.namespace, config.name, settings, project_dir)

  log(f'Dataset "{config.name}" written to {output_dir}')

  return output_dir
