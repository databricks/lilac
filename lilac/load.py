"""A script to load a dataset or set of datasets from a config for a Lilac instance.

Usage:

poetry run python -m lilac.load \
  --project_dir=demo_data \
  --config_path=lilac_hf_space.yml
"""

import gc
import os
import pathlib
import shutil
from typing import Optional, Union

import psutil
from distributed import Client

from .concepts.db_concept import DiskConceptDB, DiskConceptModelDB
from .config import Config, EmbeddingConfig, SignalConfig, read_config
from .data.dataset_duckdb import DatasetDuckDB
from .db_manager import get_dataset, list_datasets, remove_dataset_from_cache
from .env import get_project_dir
from .load_dataset import process_source
from .project import PROJECT_CONFIG_FILENAME
from .schema import ROWID, PathTuple
from .tasks import (
  TaskManager,
  TaskStepId,
  TaskStepInfo,
  TaskType,
  set_worker_next_step,
  set_worker_steps,
)
from .utils import DebugTimer, get_datasets_dir, log


def load(
  project_dir: Optional[Union[str, pathlib.Path]] = None,
  config: Optional[Union[str, pathlib.Path, Config]] = None,
  overwrite: bool = False,
  task_manager: Optional[TaskManager] = None,
  load_task_id: Optional[str] = None,
) -> None:
  """Load a project from a project configuration.

  Args:
    project_dir: The path to the project directory for where to create the dataset. If not defined,
      uses the project directory from `LILAC_PROJECT_DIR` or [deprecated] `LILAC_DATA_PATH`. The
      project_dir can be set globally with `set_project_dir`.
    config: A Lilac config or the path to a json or yml file describing the configuration. The
      contents should be an instance of `lilac.Config` or `lilac.DatasetConfig`. When not defined,
      uses `LILAC_PROJECT_DIR`/lilac.yml.
    overwrite: When True, runs all data from scratch, overwriting existing data. When false, only
      load new datasets, embeddings, and signals.
    task_manager: The task manager to use. If not defined, creates a new task manager.
    load_task_id: The load task id if load is called from a task, which happens during server
      bootup.
  """
  project_dir = project_dir or get_project_dir()
  if not project_dir:
    raise ValueError(
      '`project_dir` must be defined. Please pass a `project_dir` or set it '
      'globally with `set_project_dir(path)`'
    )

  # Turn off debug logging.
  if 'DEBUG' in os.environ:
    del os.environ['DEBUG']
  # Use views to avoid loading duckdb tables into RAM since we aren't query heavy.
  os.environ['DUCKDB_USE_VIEWS'] = '1'

  if not isinstance(config, Config):
    config_path = config or os.path.join(project_dir, PROJECT_CONFIG_FILENAME)
    config = read_config(config_path)

  # Use threads instead of processes to avoid running out of RAM.
  if not task_manager:
    # Explicitly create a dask client in sync mode.
    total_memory_gb = psutil.virtual_memory().total / (1024**3) * 2 / 3
    task_manager = TaskManager(Client(memory_limit=f'{total_memory_gb} GB', processes=False))

  if overwrite:
    shutil.rmtree(get_datasets_dir(project_dir), ignore_errors=True)

  existing_datasets = [f'{d.namespace}/{d.dataset_name}' for d in list_datasets(project_dir)]

  if load_task_id:
    set_worker_steps(
      load_task_id,
      [
        TaskStepInfo(description='Loading datasets...'),
        TaskStepInfo(description='Updating dataset settings...'),
        TaskStepInfo(description='Computing embeddings...'),
        TaskStepInfo(description='Computing signals...'),
        TaskStepInfo(description='Computing model caches...'),
      ],
    )

  log()
  log('*** Load datasets ***')
  if overwrite:
    datasets_to_load = config.datasets
  else:
    datasets_to_load = [
      d for d in config.datasets if f'{d.namespace}/{d.name}' not in existing_datasets
    ]
    skipped_datasets = [
      d for d in config.datasets if f'{d.namespace}/{d.name}' in existing_datasets
    ]
    log('Skipping loaded datasets:', ', '.join([d.name for d in skipped_datasets]))

  with DebugTimer(f'Loading datasets: {", ".join([d.name for d in datasets_to_load])}'):
    dataset_task_ids: list[str] = []
    for d in datasets_to_load:
      shutil.rmtree(os.path.join(project_dir, d.name), ignore_errors=True)
      task_id = task_manager.task_id(
        f'Load dataset {d.namespace}/{d.name}', type=TaskType.DATASET_LOAD
      )
      task_manager.execute(task_id, process_source, project_dir, d, (task_id, 0))
      dataset_task_ids.append(task_id)
    task_manager.wait(dataset_task_ids)

  log()
  total_num_rows = 0
  for d in datasets_to_load:
    dataset = DatasetDuckDB(d.namespace, d.name, project_dir=project_dir)
    num_rows = dataset.select_rows([ROWID], limit=1).total_num_rows
    log(f'{d.namespace}/{d.name} loaded with {num_rows:,} rows.')

    # Free up RAM.
    del dataset

    total_num_rows += num_rows

  log(f'Done loading {len(datasets_to_load)} datasets with {total_num_rows:,} rows.')
  if load_task_id:
    set_worker_next_step(load_task_id)

  log('*** Dataset settings ***')
  for d in config.datasets:
    if d.settings:
      dataset = DatasetDuckDB(d.namespace, d.name, project_dir=project_dir)
      dataset.update_settings(d.settings)
      del dataset

  if load_task_id:
    set_worker_next_step(load_task_id)

  log()
  log('*** Compute embeddings ***')
  with DebugTimer('Loading embeddings'):
    for d in config.datasets:
      dataset = DatasetDuckDB(d.namespace, d.name, project_dir=project_dir)
      manifest = dataset.manifest()

      embedding_task_ids: list[str] = []
      # If embeddings are explicitly set, use only those.
      embeddings = d.embeddings or []
      # If embeddings are not explicitly set, use the media paths and preferred embedding from
      # settings.
      if not embeddings:
        if d.settings and d.settings.ui:
          for path in d.settings.ui.media_paths or []:
            if d.settings.preferred_embedding:
              embeddings.append(
                EmbeddingConfig(path=path, embedding=d.settings.preferred_embedding)
              )
      for e in embeddings:
        field = manifest.data_schema.get_field(e.path)
        embedding_field = (field.fields or {}).get(e.embedding)
        if embedding_field is None or overwrite:
          task_id = task_manager.task_id(f'Compute embedding {e.embedding} on {d.name}:{e.path}')
          task_manager.execute(
            task_id, _compute_embedding, d.namespace, d.name, e, project_dir, (task_id, 0)
          )
          embedding_task_ids.append(task_id)
        else:
          log(f'Embedding {e.embedding} already exists for {d.name}:{e.path}. Skipping.')

      del dataset
      gc.collect()

      # Wait for all embeddings for each dataset to reduce the memory pressure.
      task_manager.wait(embedding_task_ids)

  if load_task_id:
    set_worker_next_step(load_task_id)

  log()
  log('*** Compute signals ***')
  with DebugTimer('Computing signals'):
    for d in config.datasets:
      dataset = DatasetDuckDB(d.namespace, d.name, project_dir=project_dir)
      manifest = dataset.manifest()

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
          field = manifest.data_schema.get_field(s.path)
          signal_field = (field.fields or {}).get(s.signal.key(is_computed_signal=True))
          if signal_field is None or overwrite:
            task_id = task_manager.task_id(f'Compute signal {s.signal} on {d.name}:{s.path}')
            task_manager.execute(
              task_id, _compute_signal, d.namespace, d.name, s, project_dir, (task_id, 0), overwrite
            )
            # Wait for each signal to reduce memory pressure.
            task_manager.wait([task_id])
          else:
            log(f'Signal {s.signal} already exists for {d.name}:{s.path}. Skipping.')

      del dataset
      gc.collect()

  if load_task_id:
    set_worker_next_step(load_task_id)

  log()
  log('*** Compute model caches ***')
  with DebugTimer('Computing model caches'):
    concept_db = DiskConceptDB(project_dir)
    concept_model_db = DiskConceptModelDB(concept_db, project_dir=project_dir)
    if config.concept_model_cache_embeddings:
      for concept_info in concept_db.list():
        for embedding in config.concept_model_cache_embeddings:
          log('Syncing concept model cache:', concept_info, embedding)
          concept_model_db.sync(
            concept_info.namespace, concept_info.name, embedding_name=embedding, create=True
          )

  if load_task_id:
    set_worker_next_step(load_task_id)

  log()
  log('Done!')


def _compute_signal(
  namespace: str,
  name: str,
  signal_config: SignalConfig,
  project_dir: Union[str, pathlib.Path],
  task_step_id: TaskStepId,
  overwrite: bool = False,
) -> None:
  os.environ['DUCKDB_USE_VIEWS'] = '1'

  # Turn off debug logging.
  if 'DEBUG' in os.environ:
    del os.environ['DEBUG']

  dataset = get_dataset(namespace, name, project_dir)
  dataset.compute_signal(
    signal=signal_config.signal,
    path=signal_config.path,
    overwrite=overwrite,
    task_step_id=task_step_id,
  )

  # Free up RAM.
  remove_dataset_from_cache(namespace, name)
  del dataset
  gc.collect()


def _compute_embedding(
  namespace: str,
  name: str,
  embedding_config: EmbeddingConfig,
  project_dir: str,
  task_step_id: TaskStepId,
) -> None:
  os.environ['DUCKDB_USE_VIEWS'] = '1'

  # Turn off debug logging.
  if 'DEBUG' in os.environ:
    del os.environ['DEBUG']

  dataset = get_dataset(namespace, name, project_dir)
  dataset.compute_embedding(
    embedding=embedding_config.embedding,
    path=embedding_config.path,
    overwrite=True,
    task_step_id=task_step_id,
  )
  remove_dataset_from_cache(namespace, name)
  del dataset
  gc.collect()
