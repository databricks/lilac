"""Loaders for managing the datasets on the Lilac demo."""

import gc
import os
import pathlib
import shutil
from typing import Optional, Union

from .concepts.db_concept import DiskConceptDB, DiskConceptModelDB
from .config import Config, EmbeddingConfig, SignalConfig, read_config
from .data.dataset_duckdb import DatasetDuckDB
from .dataset_format import DatasetFormatInputSelector, get_dataset_format_cls
from .db_manager import get_dataset, list_datasets, remove_dataset_from_cache
from .env import get_project_dir
from .load_dataset import process_source
from .project import PROJECT_CONFIG_FILENAME
from .schema import PathTuple
from .signal import TextEmbeddingSignal, get_signal_by_type, get_signal_cls
from .utils import DebugTimer, get_datasets_dir, log


def load(
  project_dir: Optional[Union[str, pathlib.Path]] = None,
  config: Optional[Union[str, pathlib.Path, Config]] = None,
  overwrite: bool = False,
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
    execution_type: The execution type for the task manager. Can be 'processes' or 'threads'.
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

  if not isinstance(config, Config):
    config_path = config or os.path.join(project_dir, PROJECT_CONFIG_FILENAME)
    config = read_config(config_path)

  if overwrite:
    shutil.rmtree(get_datasets_dir(project_dir), ignore_errors=True)

  existing_datasets = [f'{d.namespace}/{d.dataset_name}' for d in list_datasets(project_dir)]

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
    for d in datasets_to_load:
      shutil.rmtree(os.path.join(project_dir, d.name), ignore_errors=True)
      process_source(project_dir, d)

  log()
  total_num_rows = 0
  for d in datasets_to_load:
    dataset = DatasetDuckDB(d.namespace, d.name, project_dir=project_dir)
    num_rows = dataset.count()
    log(f'{d.namespace}/{d.name} loaded with {num_rows:,} rows.')

    # Free up RAM.
    del dataset

    total_num_rows += num_rows

  log(f'Done loading {len(datasets_to_load)} datasets with {total_num_rows:,} rows.')

  log('*** Dataset settings ***')
  for d in config.datasets:
    if d.settings:
      dataset = DatasetDuckDB(d.namespace, d.name, project_dir=project_dir)
      dataset.update_settings(d.settings)
      del dataset

  log()
  log('*** Compute embeddings ***')
  with DebugTimer('Loading embeddings'):
    for d in config.datasets:
      dataset = DatasetDuckDB(d.namespace, d.name, project_dir=project_dir)
      manifest = dataset.manifest()

      embeddings = d.embeddings or []
      for e in embeddings:
        field = manifest.data_schema.get_field(e.path)
        embedding_field = (field.fields or {}).get(e.embedding)
        if embedding_field is None or overwrite:
          _compute_embedding(d.namespace, d.name, e, project_dir, config.use_garden)
        else:
          log(f'Embedding {e.embedding} already exists for {d.name}:{e.path}. Skipping.')

      del dataset
      gc.collect()

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
            _compute_signal(
              d.namespace,
              d.name,
              s,
              project_dir,
              config.use_garden,
              overwrite,
            )
          else:
            log(f'Signal {s.signal} already exists for {d.name}:{s.path}. Skipping.')

      del dataset
      gc.collect()

  log()
  log('*** Compute clusters ***')
  with DebugTimer('Computing clusters'):
    for c in config.clusters:
      if not any(
        c.dataset_namespace == d.namespace and c.dataset_name == d.name for d in config.datasets
      ):
        print('Skipping cluster for non-existent dataset:', c)
        continue
      dataset = DatasetDuckDB(c.dataset_namespace, c.dataset_name, project_dir=project_dir)
      manifest = dataset.manifest()
      schema = manifest.data_schema
      # Try to find the cluster if it is precomputed.
      for path, node in schema.all_fields:
        if node.cluster is not None and (
          node.cluster.input_path == c.input_path
          or (
            node.cluster.input_format_selector
            and c.input_selector
            and (
              node.cluster.input_format_selector.format == c.input_selector.format
              and node.cluster.input_format_selector.selector == c.input_selector.selector
            )
          )
        ):
          log('Cluster already computed:', c)
          break
      else:
        # No precomputed cluster found.
        log('Computing cluster:', c)

        cluster_input: Optional[Union[DatasetFormatInputSelector, PathTuple]] = c.input_path
        if c.input_selector:
          format_cls = get_dataset_format_cls(c.input_selector.format)
          if format_cls is None:
            raise ValueError(f'Unknown format: {c.input_selector.format}')

          format = format_cls()
          if format != manifest.dataset_format:
            raise ValueError(
              f'Cluster input format {c.input_selector.format} does not match '
              f'dataset format {manifest.dataset_format}'
            )

          cluster_input = format_cls.input_selectors[c.input_selector.selector]

        assert cluster_input is not None
        dataset.cluster(
          cluster_input,
          output_path=c.output_path,
          min_cluster_size=c.min_cluster_size,
          use_garden=config.use_garden,
          topic_fn=None,
          category_fn=None,
        )

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

  log()
  log('Done!')


def _compute_signal(
  namespace: str,
  name: str,
  signal_config: SignalConfig,
  project_dir: Union[str, pathlib.Path],
  use_garden: bool,
  overwrite: bool = False,
) -> None:
  # Turn off debug logging.
  if 'DEBUG' in os.environ:
    del os.environ['DEBUG']

  dataset = get_dataset(namespace, name, project_dir)
  signal = get_signal_cls(signal_config.signal.name)
  assert signal is not None

  dataset.compute_signal(
    signal=signal_config.signal,
    path=signal_config.path,
    overwrite=overwrite,
    use_garden=use_garden and signal.supports_garden,
  )

  # Free up RAM.
  remove_dataset_from_cache(namespace, name)
  del dataset
  gc.collect()


def _compute_embedding(
  namespace: str,
  name: str,
  embedding_config: EmbeddingConfig,
  project_dir: Union[str, pathlib.Path],
  use_garden: bool,
) -> None:
  # Turn off debug logging.
  if 'DEBUG' in os.environ:
    del os.environ['DEBUG']

  dataset = get_dataset(namespace, name, project_dir)

  embedding = get_signal_by_type(embedding_config.embedding, TextEmbeddingSignal)
  dataset.compute_embedding(
    embedding=embedding_config.embedding,
    path=embedding_config.path,
    overwrite=True,
    use_garden=use_garden and embedding.supports_garden,
  )
  remove_dataset_from_cache(namespace, name)
  del dataset
  gc.collect()
