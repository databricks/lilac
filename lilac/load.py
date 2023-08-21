"""A script to load a dataset or set of datasets from a config for a Lilac instance.

Usage:

poetry run python -m lilac.load \
  --output_dir=demo_data \
  --config_path=lilac_hf_space.yml
"""

import gc
import os
import shutil

import click
import dask
import psutil
from distributed import Client

from .concepts.db_concept import DiskConceptDB, DiskConceptModelDB
from .config import EmbeddingConfig, SignalConfig, read_config
from .data.dataset_duckdb import DatasetDuckDB
from .data_loader import process_source
from .db_manager import get_dataset, list_datasets, remove_dataset_from_cache
from .schema import ROWID, PathTuple
from .tasks import TaskManager, TaskStepId
from .utils import DebugTimer, get_datasets_dir


@click.command()
@click.option(
  '--output_dir', required=True, type=str, help='The output directory to write files to.')
@click.option(
  '--config_path',
  required=True,
  type=str,
  help='The path to a json or yml file describing the configuration. '
  'The file contents should be an instance of `lilac.Config` or `lilac.DatasetConfig`.')
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
  # Use views to avoid loading duckdb tables into RAM since we aren't query heavy.
  os.environ['DUCKDB_USE_VIEWS'] = '1'

  config = read_config(config_path)

  # Explicitly create a dask client in sync mode.
  dask.config.set({'distributed.worker.daemon': False})
  total_memory_gb = psutil.virtual_memory().total / (1024**3) * 2 / 3
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
      task_manager.execute(task_id, process_source, output_dir, d, (task_id, 0))
    task_manager.wait()

  print()
  total_num_rows = 0
  for d in datasets_to_load:
    dataset = DatasetDuckDB(d.namespace, d.name)
    num_rows = dataset.select_rows([ROWID], limit=1).total_num_rows
    print(f'{d.namespace}/{d.name} loaded with {num_rows:,} rows.')

    # Free up RAM.
    del dataset

    total_num_rows += num_rows

  print(f'Done loading {len(datasets_to_load)} datasets with {total_num_rows:,} rows.')

  print('*** Dataset settings ***')
  for d in config.datasets:
    if d.settings:
      dataset = DatasetDuckDB(d.namespace, d.name)
      dataset.update_settings(d.settings)

  print()
  print('*** Compute embeddings ***')
  with DebugTimer('Loading embeddings'):
    for d in config.datasets:
      dataset = DatasetDuckDB(d.namespace, d.name)

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
        if e not in dataset.config().embeddings:
          print('scheduling', e)
          task_id = task_manager.task_id(f'Compute embedding {e.embedding} on {d.name}:{e.path}')
          task_manager.execute(task_id, _compute_embedding, d.namespace, d.name, e, output_dir,
                               overwrite, (task_id, 0))
        else:
          print(f'Embedding {e.embedding} already exists for {d.name}:{e.path}. Skipping.')

      del dataset

      # Wait for all embeddings for each dataset to reduce the memory pressure.
      task_manager.wait()

  print()
  print('*** Compute signals ***')
  with DebugTimer('Computing signals'):
    for d in config.datasets:
      dataset = DatasetDuckDB(d.namespace, d.name)

      # If signals are explicitly set, use only those.
      signals = d.signals or []
      # If signals are not explicitly set, use the media paths and config.signals.
      if not signals:
        if d.settings and d.settings.ui:
          for path in d.settings.ui.media_paths or []:
            for signal in config.signals or []:
              signals.append(SignalConfig(path=path, signal=signal))

      # Separate signals by path to avoid computing the same signal in parallel, which can cause
      # issues with taking too much RAM.
      path_signals: dict[PathTuple, list[SignalConfig]] = {}
      for s in signals:
        path_signals.setdefault(s.path, []).append(s)

      for path, signals in path_signals.items():
        for s in signals:
          if s not in dataset.config().signals:
            task_id = task_manager.task_id(f'Compute signal {s.signal} on {d.name}:{s.path}')
            task_manager.execute(task_id, _compute_signal, d.namespace, d.name, s, output_dir,
                                 overwrite, (task_id, 0))
          else:
            print(f'Signal {s.signal} already exists for {d.name}:{s.path}. Skipping.')

        # Wait for all signals for each path to reduce the memory pressure.
        task_manager.wait()

      del dataset

  print()
  print('*** Compute model caches ***')
  with DebugTimer('Computing model caches'):
    concept_db = DiskConceptDB(output_dir)
    concept_model_db = DiskConceptModelDB(concept_db)
    if config.concept_model_cache_embeddings:
      for concept_info in concept_db.list():
        for embedding in config.concept_model_cache_embeddings:
          concept_model_db.sync(
            concept_info.namespace, concept_info.name, embedding_name=embedding, create=True)

  print()
  print('Done!')

  if old_data_path:
    os.environ['LILAC_DATA_PATH'] = old_data_path


def _compute_signal(namespace: str, name: str, signal_config: SignalConfig, output_dir: str,
                    overwrite: bool, task_step_id: TaskStepId) -> None:
  os.environ['LILAC_DATA_PATH'] = output_dir
  os.environ['DUCKDB_USE_VIEWS'] = '1'

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

  # Free up RAM.
  remove_dataset_from_cache(namespace, name)
  del dataset
  gc.collect()


def _compute_embedding(namespace: str, name: str, embedding_config: EmbeddingConfig,
                       output_dir: str, overwrite: bool, task_step_id: TaskStepId) -> None:
  os.environ['LILAC_DATA_PATH'] = output_dir
  os.environ['DUCKDB_USE_VIEWS'] = '1'

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

  remove_dataset_from_cache(namespace, name)
  del dataset
  gc.collect()


if __name__ == '__main__':
  load_command()
