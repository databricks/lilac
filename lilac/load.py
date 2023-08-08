"""A script to load a dataset or set of datasets from a config for a Lilac instance.

Usage:

poetry run python -m lilac.load \
  --output_dir=demo_data \
  --config_path=demo.yml
"""

import gc
import json
import os
import pathlib
import shutil

import click
import dask
import psutil
import yaml
from distributed import Client

from .config import Config, EmbeddingConfig, SignalConfig
from .data_loader import process_source
from .db_manager import get_dataset
from .schema import UUID_COLUMN
from .tasks import TaskManager, TaskStepId
from .utils import DebugTimer, get_datasets_dir, list_datasets


@click.command()
@click.option(
  '--output_dir', required=True, type=str, help='The output directory to write files to.')
@click.option(
  '--config_path',
  required=True,
  type=str,
  help='The path to a json or yml file describing the configuration. '
  'The file contents should be an instance of `lilac.Config`.')
@click.option(
  '--overwrite',
  help='When True, runs all all data from scratch, overwriting existing data. When false, only'
  'load new datasets, embeddings, and signals.',
  type=bool,
  is_flag=True,
  default=False)
def load_command(output_dir: str, config_path: str, overwrite: bool) -> None:
  """Run the source loader as a binary."""
  load(output_dir, config_path, overwrite)


def load(output_dir: str, config_path: str, overwrite: bool) -> None:
  """Run the source loader as a binary."""
  old_data_path = os.environ.get('LILAC_DATA_PATH')
  os.environ['LILAC_DATA_PATH'] = output_dir
  # Turn off debug logging.
  del os.environ['DEBUG']

  config_ext = pathlib.Path(config_path).suffix
  if config_ext in ['.yml', '.yaml']:
    with open(config_path, 'r') as f:
      config_dict = yaml.safe_load(f)
  elif config_ext in ['.json']:
    with open(config_path, 'r') as f:
      config_dict = json.load(f)
  else:
    raise ValueError(f'Unsupported config file extension: {config_ext}')

  config = Config(**config_dict)

  # Explicitly create a dask client in sync mode.
  dask.config.set({'distributed.worker.daemon': False})
  total_memory_gb = psutil.virtual_memory().total / (1024**3)
  task_manager = TaskManager(Client(memory_limit=f'{total_memory_gb} GB'))

  if overwrite:
    shutil.rmtree(get_datasets_dir(output_dir), ignore_errors=True)

  existing_datasets = [f'{d.namespace}/{d.dataset_name}' for d in list_datasets(output_dir)]

  print()
  print('*** Load datasets ***')
  if overwrite:
    datasets_to_load = config.datasets
  else:
    datasets_to_load = [
      d for d in config.datasets if f'{d.namespace}/{d.name}' not in existing_datasets
    ]
    skipped_datasets = [
      d for d in config.datasets if f'{d.namespace}/{d.name}' in existing_datasets
    ]
    print('Skipping loaded datasets:', ', '.join([d.name for d in skipped_datasets]))

  with DebugTimer(f'Loading datasets: {", ".join([d.name for d in datasets_to_load])}'):
    for d in datasets_to_load:
      shutil.rmtree(os.path.join(output_dir, d.name), ignore_errors=True)
      task_id = task_manager.task_id(f'Load dataset {d.namespace}/{d.name}')
      task_manager.execute(task_id, process_source, output_dir, d.namespace, d.name, d.source,
                           (task_id, 0))

    task_manager.wait()

  print()
  total_num_rows = 0
  for d in datasets_to_load:
    num_rows = get_dataset(d.namespace, d.name).select_rows([UUID_COLUMN], limit=1).total_num_rows
    print(f'{d.namespace}/{d.name} loaded with {num_rows:,} rows.')
    gc.collect()
    total_num_rows += num_rows

  print(f'Done loading {len(datasets_to_load)} datasets with {total_num_rows:,} rows.')

  print('*** Dataset settings ***')
  for d in config.datasets:
    if d.settings:
      dataset = get_dataset(d.namespace, d.name)
      dataset.update_settings(d.settings)

  print()
  print('*** Compute embeddings ***')
  with DebugTimer('Loading embeddings'):
    for d in config.datasets:
      # If embeddings are explicitly set, use only those.
      embeddings = d.embeddings or []
      # If embeddings are not explicitly set, use the media paths and preferred embedding from
      # settings.
      if not embeddings:
        if d.settings and d.settings.ui:
          for path in d.settings.ui.media_paths or []:
            if d.settings.preferred_embedding:
              embeddings.append(
                EmbeddingConfig(path=path, embedding=d.settings.preferred_embedding))
      for e in embeddings:
        task_id = task_manager.task_id(f'Compute embedding {e.embedding} on {e.path}')
        task_manager.execute(task_id, _compute_embedding, d.namespace, d.name, e, output_dir,
                             overwrite, (task_id, 0))
    task_manager.wait()

  print()
  print('*** Compute signals ***')
  with DebugTimer('Computing signals'):
    for d in config.datasets:
      # If signals are explicitly set, use only those.
      signals = d.signals or []
      # If signals are not explicitly set, use the media paths and config.signals.
      if not signals:
        if d.settings and d.settings.ui:
          for path in d.settings.ui.media_paths or []:
            for signal in config.signals or []:
              signals.append(SignalConfig(path=path, signal=signal))

      for s in signals:
        task_id = task_manager.task_id(f'Compute signal {s.signal} on {s.path}')
        task_manager.execute(task_id, _compute_signal, d.namespace, d.name, s, output_dir,
                             overwrite, (task_id, 0))
    task_manager.wait()

  print()
  print('Done!')

  if old_data_path:
    os.environ['LILAC_DATA_PATH'] = old_data_path


def _compute_signal(namespace: str, name: str, signal_config: SignalConfig, output_dir: str,
                    overwrite: bool, task_step_id: TaskStepId) -> None:
  os.environ['LILAC_DATA_PATH'] = output_dir
  # Turn off debug logging.
  if 'DEBUG' in os.environ:
    del os.environ['DEBUG']

  compute_signal = False
  if overwrite:
    compute_signal = True

  dataset = get_dataset(namespace, name)

  if not compute_signal:
    field = dataset.manifest().data_schema.get_field(signal_config.path)
    signal_field = (field.fields or {}).get(signal_config.signal.key())
    if not signal_field or signal_field.signal != signal_config.signal.dict():
      compute_signal = True
  if compute_signal:
    dataset.compute_signal(signal_config.signal, signal_config.path, task_step_id)

  gc.collect()


def _compute_embedding(namespace: str, name: str, embedding_config: EmbeddingConfig,
                       output_dir: str, overwrite: bool, task_step_id: TaskStepId) -> None:
  os.environ['LILAC_DATA_PATH'] = output_dir
  # Turn off debug logging.
  if 'DEBUG' in os.environ:
    del os.environ['DEBUG']

  compute_embedding = False
  if overwrite:
    compute_embedding = True

  dataset = get_dataset(namespace, name)
  if not compute_embedding:
    field = dataset.manifest().data_schema.get_field(embedding_config.path)
    embedding_field = (field.fields or {}).get(embedding_config.embedding)
    if not embedding_field:
      compute_embedding = True

  if compute_embedding:
    dataset.compute_embedding(embedding_config.embedding, embedding_config.path, task_step_id)

  gc.collect()


if __name__ == '__main__':
  load_command()
