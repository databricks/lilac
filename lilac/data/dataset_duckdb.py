"""The DuckDB implementation of the dataset database."""
import functools
import gc
import glob
import inspect
import itertools
import json
import math
import os
import pathlib
import re
import shutil
import sqlite3
import tempfile
import threading
import urllib.parse
from contextlib import closing
from datetime import datetime
from importlib import metadata
from typing import Any, Callable, Iterable, Iterator, Literal, Optional, Sequence, Union, cast

import duckdb
import numpy as np
import pandas as pd
import pyarrow as pa
import yaml
from pandas.api.types import is_object_dtype
from pydantic import BaseModel, SerializeAsAny, field_validator
from typing_extensions import override

from ..auth import UserInfo
from ..batch_utils import deep_flatten, deep_unflatten
from ..config import (
  OLD_CONFIG_FILENAME,
  DatasetConfig,
  EmbeddingConfig,
  SignalConfig,
  get_dataset_config,
)
from ..db_manager import remove_dataset_from_cache
from ..embeddings.vector_store import VectorDBIndex
from ..env import env
from ..project import (
  add_project_dataset_config,
  add_project_embedding_config,
  add_project_signal_config,
  delete_project_dataset_config,
  delete_project_signal_config,
  read_project_config,
)
from ..schema import (
  BOOLEAN,
  EMBEDDING,
  MANIFEST_FILENAME,
  PATH_WILDCARD,
  ROWID,
  SPAN_KEY,
  STRING,
  STRING_SPAN,
  TEXT_SPAN_END_FEATURE,
  TEXT_SPAN_START_FEATURE,
  TIMESTAMP,
  VALUE_KEY,
  Bin,
  Field,
  Item,
  MapFn,
  MapInfo,
  MapType,
  Path,
  PathKey,
  PathTuple,
  RichData,
  Schema,
  arrow_schema_to_schema,
  column_paths_match,
  is_float,
  is_integer,
  is_ordinal,
  is_temporal,
  merge_schemas,
  normalize_path,
  signal_type_supports_dtype,
)
from ..signal import Signal, TextEmbeddingSignal, VectorSignal, get_signal_by_type, resolve_signal
from ..signals.concept_labels import ConceptLabelsSignal
from ..signals.concept_scorer import ConceptSignal
from ..signals.filter_mask import FilterMaskSignal
from ..signals.semantic_similarity import SemanticSimilaritySignal
from ..signals.substring_search import SubstringSignal
from ..source import NoSource, SourceManifest
from ..tasks import TaskStepId, get_is_dask_worker, get_task_manager, progress
from ..utils import (
  DebugTimer,
  delete_file,
  get_dataset_output_dir,
  get_lilac_cache_dir,
  log,
  open_file,
)
from . import dataset
from .dataset import (
  BINARY_OPS,
  LIST_OPS,
  MAX_TEXT_LEN_DISTINCT_COUNT,
  SAMPLE_AVG_TEXT_LENGTH,
  TOO_MANY_DISTINCT,
  UNARY_OPS,
  BinaryOp,
  Column,
  ColumnId,
  Dataset,
  DatasetManifest,
  FeatureListValue,
  FeatureValue,
  Filter,
  FilterLike,
  GroupsSortBy,
  MediaResult,
  Search,
  SearchResultInfo,
  SelectGroupsResult,
  SelectRowsResult,
  SelectRowsSchemaResult,
  SelectRowsSchemaUDF,
  SortOrder,
  SortResult,
  StatsResult,
  column_from_identifier,
  dataset_config_from_manifest,
  get_map_parquet_id,
  make_signal_parquet_id,
)
from .dataset_utils import (
  count_primitives,
  create_signal_schema,
  flatten_keys,
  get_parquet_filename,
  schema_contains_path,
  sparse_to_dense_compute,
  wrap_in_dicts,
  write_embeddings_to_disk,
)

SIGNAL_MANIFEST_FILENAME = 'signal_manifest.json'
MAP_MANIFEST_SUFFIX = 'map_manifest.json'
LABELS_SQLITE_SUFFIX = '.labels.sqlite'
DATASET_SETTINGS_FILENAME = 'settings.json'
SOURCE_VIEW_NAME = 'source'

SQLITE_LABEL_COLNAME = 'label'
SQLITE_CREATED_COLNAME = 'created'

NUM_AUTO_BINS = 15

BINARY_OP_TO_SQL: dict[BinaryOp, str] = {
  'equals': '=',
  'not_equal': '!=',
  'greater': '>',
  'greater_equal': '>=',
  'less': '<',
  'less_equal': '<=',
}


class MapFnJobRequest(BaseModel):
  """The job information passed to worker for a map function."""

  job_id: int
  job_count: int


class DuckDBSearchUDF(BaseModel):
  """The transformation of searches to column UDFs."""

  udf: Column
  search_path: PathTuple
  output_path: PathTuple
  sort: Optional[tuple[PathTuple, SortOrder]] = None


class DuckDBSearchUDFs(BaseModel):
  """The transformation of searches to column UDFs with sorts."""

  udfs: list[Column]
  output_paths: list[PathTuple]
  sorts: list[tuple[PathTuple, SortOrder]]


class SignalManifest(BaseModel):
  """The manifest that describes a signal computation including schema and parquet files."""

  # List of a parquet filepaths storing the data. The paths are relative to the manifest.
  files: list[str]

  # An identifier for this parquet table. Will be used as the view name in SQL.
  parquet_id: str

  data_schema: Schema
  signal: SerializeAsAny[Signal]

  # The column path that this signal is derived from.
  enriched_path: PathTuple

  # The name of the vector store. Present when the signal is an embedding.
  vector_store: Optional[str] = None

  # The lilac python version that produced this signal.
  py_version: Optional[str] = None

  @field_validator('signal', mode='before')
  @classmethod
  def parse_signal(cls, signal: dict) -> Signal:
    """Parse a signal to its specific subclass instance."""
    return resolve_signal(signal)


class MapManifest(BaseModel):
  """The manifest that describes a signal computation including schema and parquet files."""

  # List of a parquet filepaths storing the data. The paths are relative to the manifest.
  files: list[str]

  # An identifier for this parquet table. Will be used as the view name in SQL.
  parquet_id: str

  data_schema: Schema

  # The lilac python version that produced this map output.
  py_version: Optional[str] = None


class DuckDBMapOutput:
  """The output of a map computation."""

  def __init__(self, pyarrow_reader: pa.RecordBatchReader, output_column: str):
    self.pyarrow_reader = pyarrow_reader
    self.output_column = output_column

  def __iter__(self) -> Iterator[Item]:
    for batch in self.pyarrow_reader:
      yield from (row[self.output_column] for row in batch.to_pylist())

    # TODO(nsthorat): Implement next() and allow multiple iterations once we actually write to
    # JSONL. We can't do this now because the memory connection to the jsonl file does not persist.
    self.pyarrow_reader.close()


class DatasetDuckDB(Dataset):
  """The DuckDB implementation of the dataset database."""

  def __init__(
    self,
    namespace: str,
    dataset_name: str,
    vector_store: str = 'hnsw',
    project_dir: Optional[Union[str, pathlib.Path]] = None,
  ):
    super().__init__(namespace, dataset_name, project_dir)
    self.dataset_path = get_dataset_output_dir(self.project_dir, namespace, dataset_name)

    # TODO: Infer the manifest from the parquet files so this is lighter weight.
    self._source_manifest = read_source_manifest(self.dataset_path)
    self._signal_manifests: list[SignalManifest] = []
    self._map_manifests: list[MapManifest] = []
    self._label_schemas: dict[str, Schema] = {}
    self.con = duckdb.connect(database=':memory:')

    # Maps a path and embedding to the vector index. This is lazily generated as needed.
    self._vector_indices: dict[tuple[PathKey, str], VectorDBIndex] = {}
    self.vector_store = vector_store
    self._manifest_lock = threading.Lock()
    self._config_lock = threading.Lock()
    self._vector_index_lock = threading.Lock()
    self._label_file_lock: dict[str, threading.Lock] = {}

    # Create a join table from all the parquet files.
    manifest = self.manifest()

    # NOTE: This block is only for backwards compatibility.
    # Make sure the project reflects the dataset.
    project_config = read_project_config(self.project_dir)
    existing_dataset_config = get_dataset_config(project_config, self.namespace, self.dataset_name)
    if not existing_dataset_config:
      dataset_config = dataset_config_from_manifest(manifest)
      # Check if the old config file exists so we remember settings.
      old_config_filepath = os.path.join(self.dataset_path, OLD_CONFIG_FILENAME)
      if os.path.exists(old_config_filepath):
        with open(old_config_filepath) as f:
          old_config = DatasetConfig(**yaml.safe_load(f))
        dataset_config.settings = old_config.settings

      add_project_dataset_config(dataset_config, self.project_dir)

  def __getstate__(self) -> dict[str, Any]:
    """Return the state to pickle. This is necessary so we can pickle the dataset when using dask.

    This serializes the arguments to the constructor only as they are used to unpickle the dataset.
    """
    return {
      'namespace': self.namespace,
      'dataset_name': self.dataset_name,
      'vector_store': self.vector_store,
      'project_dir': self.project_dir,
    }

  def __setstate__(self, state: dict[str, Any]) -> None:
    """Unpickle the dataset. We go through the constructor."""
    self.__init__(**state)  # type: ignore

  @override
  def delete(self) -> None:
    """Deletes the dataset."""
    self.con.close()
    shutil.rmtree(self.dataset_path, ignore_errors=True)
    delete_project_dataset_config(self.namespace, self.dataset_name, self.project_dir)
    remove_dataset_from_cache(self.namespace, self.dataset_name)

  def _create_view(
    self, view_name: str, files: list[str], type: Literal['parquet', 'sqlite']
  ) -> None:
    inner_select: str
    if type == 'parquet':
      inner_select = f'SELECT * FROM read_parquet({files})'
    elif type == 'sqlite':
      if len(files) > 1:
        raise ValueError('Only one sqlite file is supported.')
      inner_select = f"""
        SELECT * FROM sqlite_scan('{files[0]}', '{view_name}')
      """
    else:
      raise ValueError(f'Unknown type: {type}')

    self.con.execute(
      f"""
      CREATE OR REPLACE VIEW {_escape_col_name(view_name)} AS ({inner_select});
    """
    )

  # NOTE: This is cached, but when the latest mtime of any file in the dataset directory changes
  # the results are invalidated.
  @functools.cache
  def _recompute_joint_table(self, latest_mtime_micro_sec: int) -> DatasetManifest:
    del latest_mtime_micro_sec  # This is used as the cache key.
    merged_schema = self._source_manifest.data_schema.model_copy(deep=True)
    self._signal_manifests = []
    self._label_schemas = {}
    self._map_manifests = []
    # Make a joined view of all the column groups.
    self._create_view(
      SOURCE_VIEW_NAME,
      [os.path.join(self.dataset_path, f) for f in self._source_manifest.files],
      type='parquet',
    )

    # Add the signal column groups.
    for root, _, files in os.walk(self.dataset_path):
      for file in files:
        if file.endswith(SIGNAL_MANIFEST_FILENAME):
          with open_file(os.path.join(root, file)) as f:
            signal_manifest = SignalManifest.model_validate_json(f.read())
          self._signal_manifests.append(signal_manifest)
          signal_files = [os.path.join(root, f) for f in signal_manifest.files]
          if signal_files:
            self._create_view(signal_manifest.parquet_id, signal_files, type='parquet')
        elif file.endswith(LABELS_SQLITE_SUFFIX):
          label_name = file[0 : -len(LABELS_SQLITE_SUFFIX)]
          self._create_view(label_name, [os.path.join(root, file)], type='sqlite')
          # This mirrors the structure in DuckDBDatasetLabel.
          self._label_schemas[label_name] = Schema(
            fields={
              label_name: Field(
                fields={
                  'label': Field(dtype=STRING),
                  'created': Field(dtype=TIMESTAMP),
                },
                label=label_name,
              )
            }
          )
        elif file.endswith(MAP_MANIFEST_SUFFIX):
          with open_file(os.path.join(root, file)) as f:
            map_manifest = MapManifest.model_validate_json(f.read())
          map_files = [os.path.join(root, f) for f in map_manifest.files]
          self._create_view(map_manifest.parquet_id, map_files, type='parquet')
          if map_files:
            self._map_manifests.append(map_manifest)

    merged_schema = merge_schemas(
      [self._source_manifest.data_schema]
      + [m.data_schema for m in self._signal_manifests + self._map_manifests]
      + list(self._label_schemas.values())
    )

    # The logic below generates the following example query:
    # CREATE OR REPLACE VIEW t AS (
    #   SELECT
    #     source.*,
    #     "parquet_id1"."root_column" AS "parquet_id1",
    #     "parquet_id2"."root_column" AS "parquet_id2"
    #   FROM source JOIN "parquet_id1" USING (rowid,) JOIN "parquet_id2" USING (rowid,)
    # );
    # NOTE: "root_column" for each signal is defined as the top-level column.
    signal_column_selects = [
      (
        f'{_escape_col_name(manifest.parquet_id)}.{_escape_col_name(_root_column(manifest))} '
        f'AS {_escape_col_name(manifest.parquet_id)}'
      )
      for manifest in self._signal_manifests
      if manifest.files
    ]
    map_column_selects = [
      (
        f'{_escape_col_name(manifest.parquet_id)}.{_escape_col_name(_root_column(manifest))} '
        f'AS {_escape_col_name(manifest.parquet_id)}'
      )
      for manifest in self._map_manifests
      if manifest.files
    ]
    label_column_selects = []
    for label_name in self._label_schemas.keys():
      col_name = _escape_col_name(label_name)
      # We use a case here because labels are sparse and we don't want to return an object at all
      # when there is no label.
      label_column_selects.append(
        f"""
        (CASE WHEN {col_name}.{SQLITE_LABEL_COLNAME} IS NULL THEN NULL ELSE {{
          {SQLITE_LABEL_COLNAME}: {col_name}.{SQLITE_LABEL_COLNAME},
          {SQLITE_CREATED_COLNAME}: {col_name}.{SQLITE_CREATED_COLNAME}
        }} END) as {col_name}
      """
      )

    select_sql = ', '.join(
      [f'{SOURCE_VIEW_NAME}.*'] + signal_column_selects + map_column_selects + label_column_selects
    )

    # Get parquet ids for signals, maps, and labels.
    parquet_ids = [
      manifest.parquet_id
      for manifest in self._signal_manifests + self._map_manifests
      if manifest.files
    ] + list(self._label_schemas.keys())
    join_sql = ' '.join(
      [SOURCE_VIEW_NAME]
      + [f'LEFT JOIN {_escape_col_name(parquet_id)} USING ({ROWID})' for parquet_id in parquet_ids]
    )
    view_or_table = 'TABLE'
    # When in a dask worker, always use views to reduce memory overhead.
    if get_is_dask_worker():
      use_views = True
    else:
      use_views = bool(env('DUCKDB_USE_VIEWS', 0) or 0)

    if use_views:
      view_or_table = 'VIEW'
    sql_cmd = f"""
      CREATE OR REPLACE {view_or_table} t AS (SELECT {select_sql} FROM {join_sql})
    """
    self.con.execute(sql_cmd)
    # Get the total size of the table.
    size_query = 'SELECT COUNT() as count FROM t'
    size_query_result = cast(Any, self._query(size_query)[0])
    num_items = cast(int, size_query_result[0])

    for path, field in merged_schema.leafs.items():
      if field.dtype and field.dtype.type == 'map':
        map_dtype = cast(MapType, field.dtype)
        if map_dtype.key_type == STRING:
          # Find all the keys for this map and add them to the schema.
          self._add_map_keys_to_schema(path, field, merged_schema)

    return DatasetManifest(
      namespace=self.namespace,
      dataset_name=self.dataset_name,
      data_schema=merged_schema,
      num_items=num_items,
      source=self._source_manifest.source,
    )

  def _add_map_keys_to_schema(self, path: PathTuple, field: Field, merged_schema: Schema) -> None:
    """Adds the keys of a map to the schema."""
    value_column = 'key'
    duckdb_path = self._leaf_path_to_duckdb_path(path, merged_schema)
    inner_select = _select_sql(
      duckdb_path, flatten=False, unnest=True, path=path, schema=merged_schema
    )
    query = f"""
      SELECT DISTINCT unnest(map_keys({inner_select})) AS {value_column} FROM t
    """
    df = self._query_df(query)
    keys: list[str] = sorted(df[value_column])

    map_dtype = cast(MapType, field.dtype)
    field.fields = field.fields or {}
    for key in keys:
      field.fields[key] = Field(dtype=map_dtype.value_type)

  @override
  def manifest(self) -> DatasetManifest:
    # Use the latest modification time of all files under the dataset path as the cache key for
    # re-computing the manifest and the joined view.
    with self._manifest_lock:
      all_dataset_files = glob.iglob(os.path.join(self.dataset_path, '**'), recursive=True)
      latest_mtime = max(map(os.path.getmtime, all_dataset_files))
      latest_mtime_micro_sec = int(latest_mtime * 1e6)
      return self._recompute_joint_table(latest_mtime_micro_sec)

  def count(self, filters: Optional[list[FilterLike]] = None) -> int:
    """Count the number of rows."""
    raise NotImplementedError('count is not yet implemented for DuckDB.')

  def _get_vector_db_index(self, embedding: str, path: PathTuple) -> VectorDBIndex:
    # Refresh the manifest to make sure we have the latest signal manifests.
    self.manifest()
    index_key = (path, embedding)
    with self._vector_index_lock:
      if index_key in self._vector_indices:
        return self._vector_indices[index_key]

      manifests = [
        m
        for m in self._signal_manifests
        if schema_contains_path(m.data_schema, path)
        and m.vector_store
        and m.signal.name == embedding
      ]
      if not manifests:
        raise ValueError(f'No embedding found for path {path}.')
      if len(manifests) > 1:
        raise ValueError(f'Multiple embeddings found for path {path}. Got: {manifests}')
      manifest = manifests[0]
      if not manifest.vector_store:
        raise ValueError(
          f'Signal manifest for path {path} is not an embedding. '
          f'Got signal manifest: {manifest}'
        )

      base_path = os.path.join(
        self.dataset_path, _signal_dir(manifest.enriched_path), manifest.signal.name
      )
      path_id = f'{self.namespace}/{self.dataset_name}:{path}'
      with DebugTimer(
        f'Loading vector store "{manifest.vector_store}" for {path_id}'
        f' with embedding "{embedding}"'
      ):
        vector_index = VectorDBIndex(manifest.vector_store)
        vector_index.load(base_path)
      # Cache the vector index.
      self._vector_indices[index_key] = vector_index
      return vector_index

  def _select_iterable_values(
    self,
    unnest_input_path: Optional[PathTuple] = None,
    combine_columns: bool = False,
    resolve_span: bool = False,
    shard_cache_filepath: Optional[str] = None,
    overwrite: bool = False,
    shard_id: Optional[int] = None,
    shard_count: Optional[int] = None,
  ) -> Iterable[tuple[str, Item]]:
    """Returns an iterable of (rowid, item), discluding results in the cache filepath."""
    manifest = self.manifest()

    num_items = self.manifest().num_items
    shard_size = math.ceil(num_items / shard_count) if shard_count else num_items
    shard_start_idx = shard_id * shard_size if shard_id is not None else 0
    shard_end_idx = (
      min((shard_id + 1) * shard_size, num_items) if shard_id is not None else num_items
    )

    column: Optional[Column] = None
    cols = self._normalize_columns(
      [unnest_input_path or (PATH_WILDCARD,)], manifest.data_schema, combine_columns
    )
    select_queries: list[str] = []
    columns_to_merge: dict[str, dict[str, Column]] = {}

    unnest_column_alias: Optional[str] = None
    for column in cols:
      path = column.path

      select_sqls: list[str] = []
      final_col_name = column.alias or _unique_alias(column)
      if final_col_name not in columns_to_merge:
        columns_to_merge[final_col_name] = {}

      duckdb_paths = self._column_to_duckdb_paths(column, manifest.data_schema, combine_columns)
      span_from = self._resolve_span(path, manifest) if resolve_span or column.signal_udf else None

      for parquet_id, duckdb_path in duckdb_paths:
        sql = _select_sql(
          duckdb_path,
          flatten=False,
          unnest=False,
          path=path,
          schema=manifest.data_schema,
          empty=False,
          span_from=span_from,
        )
        column_alias = (
          final_col_name if len(duckdb_paths) == 1 else f'{final_col_name}/{parquet_id}'
        )
        if unnest_input_path:
          unnest_column_alias = column_alias

        select_sqls.append(f'{sql} AS {_escape_string_literal(column_alias)}')
        columns_to_merge[final_col_name][column_alias] = column

      if select_sqls:
        select_queries.append(', '.join(select_sqls))

      if combine_columns:
        all_columns: dict[str, Column] = {}
        for col_dict in columns_to_merge.values():
          all_columns.update(col_dict)
        columns_to_merge = {'*': all_columns}

    # Fetch the data from DuckDB.
    con = self.con.cursor()

    # Create a view for the work of the shard before anti-joining.
    con.execute(
      f"""
      CREATE OR REPLACE VIEW t_shard as (
        SELECT * FROM t
        ORDER BY {ROWID}
        LIMIT {shard_end_idx - shard_start_idx}
        OFFSET {shard_start_idx}
      );
    """
    )
    select_sql = ', '.join(select_queries)

    # Anti-join removes input rows that are already in the cache so they do not get passed to the
    # map function.
    anti_join = ''
    use_jsonl_cache = False
    if not overwrite and shard_cache_filepath and os.path.exists(shard_cache_filepath):
      with open_file(shard_cache_filepath, 'r') as f:
        # Read the first line of the file
        first_line = f.readline()
      use_jsonl_cache = True if first_line.strip() else False

    if use_jsonl_cache:
      con.execute(
        f"""
        CREATE OR REPLACE VIEW t_cache as (
          SELECT * FROM read_json_auto(
            '{shard_cache_filepath}',
            IGNORE_ERRORS=true,
            format='newline_delimited')
        );
      """
      )

      anti_join = f'ANTI JOIN t_cache USING({ROWID})'

    result = con.execute(
      f"""
      SELECT {ROWID}, {select_sql} FROM t_shard
      {anti_join}
    """
    )

    while True:
      df_chunk = result.fetch_df_chunk()
      if df_chunk.empty:
        break

      for final_col_name, temp_columns in columns_to_merge.items():
        for temp_col_name, column in temp_columns.items():
          if combine_columns:
            dest_path = _col_destination_path(column)
            spec = _split_path_into_subpaths_of_lists(dest_path)
            df_chunk[temp_col_name] = list(wrap_in_dicts(df_chunk[temp_col_name], spec))

          # If the temp col name is the same as the final name, we can skip merging. This happens
          # when we select a source leaf column.
          if temp_col_name == final_col_name:
            continue

          if final_col_name not in df_chunk:
            df_chunk[final_col_name] = df_chunk[temp_col_name]
          else:
            df_chunk[final_col_name] = merge_series(
              df_chunk[final_col_name], df_chunk[temp_col_name]
            )
          del df_chunk[temp_col_name]

      row_ids = df_chunk[ROWID].tolist()
      if combine_columns:
        # Since we aliased every column to `*`, the object will have only '*' as the key. We need
        # to elevate the all the columns under '*'.
        df_chunk = pd.DataFrame.from_records(df_chunk['*'])

      if unnest_input_path and unnest_column_alias:
        values = df_chunk[unnest_column_alias].tolist()
      else:
        values = df_chunk.to_dict('records')

      yield from zip(row_ids, values)

  def _compute_disk_cached(
    self,
    transform_fn: Union[Signal, Callable[[Iterable[Item]], Iterable[Optional[Item]]]],
    output_path: PathTuple,
    jsonl_cache_filepath: str,
    unnest_input_path: Optional[PathTuple] = None,
    overwrite: bool = False,
    combine_columns: bool = False,
    resolve_span: bool = False,
    shard_id: Optional[int] = None,
    shard_count: Optional[int] = None,
    task_step_id: Optional[TaskStepId] = None,
    task_step_description: Optional[str] = None,
  ) -> Iterable[Item]:
    manifest = self.manifest()

    os.makedirs(os.path.dirname(jsonl_cache_filepath), exist_ok=True)
    # Overwrite the file if overwrite is True.
    if overwrite and os.path.exists(jsonl_cache_filepath):
      delete_file(jsonl_cache_filepath)

    use_jsonl_cache = not overwrite and os.path.exists(jsonl_cache_filepath)

    con = self.con.cursor()

    # Compute the start index where the cache file left off.
    start_idx = 0
    if use_jsonl_cache:
      count_result = con.execute(
        f"""
        SELECT COUNT(*) FROM read_json_auto(
          '{jsonl_cache_filepath}',
          IGNORE_ERRORS=true,
          format='newline_delimited')
        """
      ).fetchone()
      if count_result:
        (start_idx,) = count_result

    rows = self._select_iterable_values(
      unnest_input_path=unnest_input_path,
      combine_columns=combine_columns,
      resolve_span=resolve_span,
      shard_cache_filepath=jsonl_cache_filepath,
      overwrite=overwrite,
      shard_id=shard_id,
      shard_count=shard_count,
    )

    # Tee the results so we can zip the row ids with the outputs.
    inputs_0, inputs_1 = itertools.tee(rows, 2)

    # Tee the values so we can use them for the deep flatten and the deep unflatten.
    input_values = (value for (_, value) in inputs_0)

    nested_spec = _split_path_into_subpaths_of_lists(output_path or ())

    output_items: Iterable[Optional[Item]]
    # Flatten the outputs back to the shape of the original data.
    # The output values are flat from the signal. This
    if unnest_input_path:
      input_values_0, input_values_1 = itertools.tee(input_values, 2)

      assert unnest_input_path is not None
      source_path = unnest_input_path

      if isinstance(transform_fn, VectorSignal):
        embedding_signal = transform_fn
        inputs_1, inputs_2 = itertools.tee(inputs_1, 2)
        vector_store = self._get_vector_db_index(embedding_signal.embedding, source_path)
        flat_keys = list(flatten_keys((rowid for (rowid, _) in inputs_2), input_values_0))
        dense_out = sparse_to_dense_compute(
          iter(flat_keys), lambda keys: embedding_signal.vector_compute(keys, vector_store)
        )
      elif isinstance(transform_fn, Signal):
        signal = transform_fn
        flat_input = cast(Iterator[Optional[RichData]], deep_flatten(input_values_0))
        dense_out = sparse_to_dense_compute(
          flat_input, lambda x: signal.compute(cast(Iterable[RichData], x))
        )
      else:
        raise ValueError(f'Unknown type of transform_fn: {type(transform_fn)}')

      output_items = deep_unflatten(dense_out, input_values_1)

    else:
      assert not isinstance(transform_fn, Signal)
      output_items = transform_fn(input_values)

    output_items = cast(Iterable[Item], wrap_in_dicts(output_items, nested_spec))

    output_items = (
      {**item, ROWID: rowid} for (rowid, _), item in zip(inputs_1, output_items) if item
    )

    # Add progress.
    if task_step_id is not None:
      output_items = progress(
        output_items,
        task_step_id=task_step_id,
        initial_id=start_idx,
        estimated_len=manifest.num_items,
        step_description=task_step_description,
      )

    output_items, jsonl_cache_items = itertools.tee(output_items, 2)
    # TODO(nsthorat): Support continuation of embeddings.
    try:
      if not isinstance(transform_fn, TextEmbeddingSignal):
        with open_file(jsonl_cache_filepath, 'a') as file:
          for item in output_items:
            json.dump(item, file)
            file.write('\n')
    except RuntimeError as e:
      # NOTE: A RuntimeError exception is thrown when the output_items iterator, which is a zip of
      # input and output items, yields a StopIterator exception.
      raise ValueError(
        'The signal generated a different number of outputs than was given as input. '
        'Please yield `None` for sparse signals. For signals that output multiple values, '
        'please yield an array for each input.'
      )
    except Exception as e:
      raise e

    return jsonl_cache_items

  def _reshard_cache(
    self,
    output_path: PathTuple,
    jsonl_cache_filepaths: list[str],
    is_tmp_output: bool = False,
    parquet_filename_prefix: Optional[str] = None,
    overwrite: bool = False,
  ) -> tuple[pa.RecordBatchReader, Schema, Optional[str]]:
    """Reshards the jsonl cache files into a single parquet file.

    When is_tmp_output is true, the results are still merged to a single iterable PyArrow reader.
    """
    # Merge all the shard outputs.
    jsonl_view_name = 'tmp_output'
    con = self.con.cursor()

    # TODO(nsthorat): Use read_json and the signal schema to speed this up and make it more precise.
    con.execute(
      f"""
      CREATE OR REPLACE VIEW {jsonl_view_name} as (
        SELECT * FROM read_json_auto(
          {jsonl_cache_filepaths},
          ignore_errors=true,
          format='newline_delimited'
        )
      );
    """
    )

    parquet_filepath: Optional[str] = None
    reader = con.execute(f'SELECT * from {jsonl_view_name}').fetch_record_batch(
      rows_per_batch=10_000
    )
    if not is_tmp_output:
      parquet_filepath = _get_parquet_filepath(
        dataset_path=self.dataset_path,
        output_path=output_path,
        parquet_filename_prefix=parquet_filename_prefix,
      )
      if overwrite and os.path.exists(parquet_filepath):
        # Delete the parquet file if it exists.
        delete_file(parquet_filepath)

      os.makedirs(os.path.dirname(parquet_filepath), exist_ok=True)

      con.execute(
        f"""COPY (SELECT * FROM '{jsonl_view_name}') TO '{parquet_filepath}' (FORMAT PARQUET);"""
      )

      con.close()

    output_schema = arrow_schema_to_schema(reader.schema)
    if ROWID in output_schema.fields:
      del output_schema.fields[ROWID]

    return reader, output_schema, parquet_filepath

  @override
  def compute_signal(
    self,
    signal: Signal,
    path: Path,
    overwrite: bool = False,
    task_step_id: Optional[TaskStepId] = None,
  ) -> None:
    if isinstance(signal, TextEmbeddingSignal):
      return self.compute_embedding(
        signal.name, path, overwrite=overwrite, task_step_id=task_step_id
      )

    input_path = normalize_path(path)

    manifest = self.manifest()

    signal_col = Column(path=input_path, alias='value', signal_udf=signal)
    output_path = _col_destination_path(signal_col, is_computed_signal=True)

    if not manifest.data_schema.has_field(input_path):
      raise ValueError(f'Cannot compute signal over non-existent path: {input_path}')
    if manifest.data_schema.get_field(input_path).dtype != STRING:
      raise ValueError('Cannot compute signal over a non-string field.')
    if manifest.data_schema.has_field(output_path) and not overwrite:
      raise ValueError('Signal already exists. Use overwrite=True to overwrite.')

    if task_step_id is None:
      # Make a dummy task step so we report progress via tqdm.
      task_step_id = ('', 0)

    # Update the project config before computing the signal.
    add_project_signal_config(
      self.namespace,
      self.dataset_name,
      SignalConfig(path=input_path, signal=signal),
      self.project_dir,
    )

    signal.setup()

    jsonl_cache_filepath = _jsonl_cache_filepath(
      namespace=self.namespace,
      dataset_name=self.dataset_name,
      key=output_path,
      project_dir=self.project_dir,
    )
    self._compute_disk_cached(
      transform_fn=signal,
      output_path=output_path,
      jsonl_cache_filepath=jsonl_cache_filepath,
      unnest_input_path=input_path,
      overwrite=overwrite,
      task_step_id=task_step_id,
      task_step_description=f'Computing signal {signal} over {input_path}',
    )

    _, _, parquet_filepath = self._reshard_cache(
      output_path=output_path,
      jsonl_cache_filepaths=[jsonl_cache_filepath],
      parquet_filename_prefix='data',
      overwrite=overwrite,
    )
    assert parquet_filepath is not None
    parquet_filename = os.path.basename(parquet_filepath)
    output_dir = os.path.dirname(parquet_filepath)

    signal_manifest_filepath = os.path.join(output_dir, SIGNAL_MANIFEST_FILENAME)

    signal_schema = create_signal_schema(signal, input_path, manifest.data_schema)

    signal_manifest = SignalManifest(
      files=[parquet_filename],
      data_schema=signal_schema,
      signal=signal,
      enriched_path=input_path,
      parquet_id=make_signal_parquet_id(signal, input_path, is_computed_signal=True),
      py_version=metadata.version('lilac'),
    )
    with open_file(signal_manifest_filepath, 'w') as f:
      f.write(signal_manifest.model_dump_json(exclude_none=True, indent=2))

    log(f'Wrote signal output to {output_dir}')

  @override
  def compute_embedding(
    self,
    embedding: str,
    path: Path,
    overwrite: bool = False,
    task_step_id: Optional[TaskStepId] = None,
  ) -> None:
    input_path = normalize_path(path)
    add_project_embedding_config(
      self.namespace,
      self.dataset_name,
      EmbeddingConfig(path=input_path, embedding=embedding),
      self.project_dir,
    )

    manifest = self.manifest()
    field = manifest.data_schema.get_field(input_path)
    if field.dtype != STRING:
      raise ValueError('Cannot compute embedding over a non-string field.')

    if task_step_id is None:
      # Make a dummy task step so we report progress via tqdm.
      task_step_id = ('', 0)

    signal = get_signal_by_type(embedding, TextEmbeddingSignal)()

    signal.setup()

    signal_col = Column(path=input_path, alias='value', signal_udf=signal)

    output_path = _col_destination_path(signal_col, is_computed_signal=True)

    jsonl_cache_filepath = _jsonl_cache_filepath(
      namespace=self.namespace,
      dataset_name=self.dataset_name,
      key=output_path,
      project_dir=self.project_dir,
    )
    output_items = self._compute_disk_cached(
      signal,
      output_path=output_path,
      jsonl_cache_filepath=jsonl_cache_filepath,
      unnest_input_path=input_path,
      overwrite=overwrite,
      task_step_id=task_step_id,
      task_step_description=f'Computing embedding {signal} over {input_path}',
    )

    output_dir = os.path.join(self.dataset_path, _signal_dir(output_path))
    signal_schema = create_signal_schema(signal, input_path, manifest.data_schema)

    row_ids = (item[ROWID] for item in output_items)

    write_embeddings_to_disk(
      vector_store=self.vector_store,
      rowids=row_ids,
      signal_items=output_items,
      output_dir=output_dir,
    )

    gc.collect()

    signal_manifest_filepath = os.path.join(output_dir, SIGNAL_MANIFEST_FILENAME)
    # If the signal manifest already exists, delete it as it will be rewritten after the new signal
    # outputs are run.
    if os.path.exists(signal_manifest_filepath):
      os.remove(signal_manifest_filepath)
      # Call manifest() to recreate all the views, otherwise this could be stale and point to a non
      # existent file.
      self.manifest()

    signal_manifest = SignalManifest(
      files=[],
      data_schema=signal_schema,
      signal=signal,
      enriched_path=input_path,
      parquet_id=make_signal_parquet_id(signal, input_path, is_computed_signal=True),
      vector_store=self.vector_store,
      py_version=metadata.version('lilac'),
    )

    with open_file(signal_manifest_filepath, 'w') as f:
      f.write(signal_manifest.model_dump_json(exclude_none=True, indent=2))

    log(f'Wrote embedding index to {output_dir}')

  @override
  def delete_signal(self, signal_path: Path) -> None:
    signal_path = normalize_path(signal_path)

    manifest = self.manifest()
    if not manifest.data_schema.has_field(signal_path):
      raise ValueError(f'Unknown signal path: {signal_path}')

    source_path = signal_path[:-1]  # Remove the inner most signal path.
    field = manifest.data_schema.get_field(signal_path)
    signal = field.signal
    if signal is None:
      raise ValueError(f'{signal_path} is not a signal.')

    # Delete the cache files.
    shard_cache_filepath = _jsonl_cache_filepath(
      namespace=self.namespace,
      dataset_name=self.dataset_name,
      key=signal_path,
      project_dir=self.project_dir,
    )
    if os.path.exists(shard_cache_filepath):
      os.remove(shard_cache_filepath)

    delete_project_signal_config(
      self.namespace,
      self.dataset_name,
      SignalConfig(path=source_path, signal=resolve_signal(signal)),
      self.project_dir,
    )

    output_dir = os.path.join(self.dataset_path, _signal_dir(signal_path))
    shutil.rmtree(output_dir, ignore_errors=True)

  def _validate_filters(
    self, filters: Sequence[Filter], col_aliases: dict[str, PathTuple], manifest: DatasetManifest
  ) -> None:
    for filter in filters:
      if filter.path[0] in col_aliases:
        # This is a filter on a column alias, which is always allowed.
        continue

      current_field = Field(fields=manifest.data_schema.fields)
      if filter.path == (ROWID,):
        return
      for path_part in filter.path:
        if path_part == VALUE_KEY:
          if not current_field.dtype:
            raise ValueError(f'Unable to filter on path {filter.path}. The field has no value.')
          continue
        if current_field.fields:
          if path_part not in current_field.fields:
            raise ValueError(
              f'Unable to filter on path {filter.path}. '
              f'Path part "{path_part}" not found in the dataset.'
            )
          current_field = current_field.fields[str(path_part)]
          continue
        elif current_field.repeated_field:
          current_field = current_field.repeated_field
          continue
        else:
          raise ValueError(
            f'Unable to filter on path {filter.path}. '
            f'Path part "{path_part}" is not defined on a primitive value.'
          )

      while current_field.repeated_field:
        current_field = current_field.repeated_field
        filter.path = (*filter.path, PATH_WILDCARD)

      if filter.op in BINARY_OPS and not current_field.dtype:
        raise ValueError(f'Unable to filter on path {filter.path}. The field has no value.')

  def _validate_udfs(self, udf_cols: Sequence[Column], source_schema: Schema) -> None:
    for col in udf_cols:
      path = col.path

      # Signal transforms must operate on a leaf field.
      leaf = source_schema.leafs.get(path)
      if not leaf or not leaf.dtype:
        raise ValueError(
          f'Leaf "{path}" not found in dataset. ' 'Signal transforms must operate on a leaf field.'
        )

      # Signal transforms must have the same dtype as the leaf field.
      signal = cast(Signal, col.signal_udf)
      if not signal_type_supports_dtype(signal.input_type, leaf.dtype):
        raise ValueError(
          f'Leaf "{path}" has dtype "{leaf.dtype}" which is not supported '
          f'by "{signal.key()}" with signal input type "{signal.input_type}".'
        )

  def _validate_selection(self, columns: Sequence[Column], select_schema: Schema) -> None:
    # Validate all the columns and make sure they exist in the `select_schema`.
    for column in columns:
      current_field = Field(fields=select_schema.fields)
      path = column.path
      if path == (ROWID,):
        return
      for path_part in path:
        if path_part == VALUE_KEY:
          if not current_field.dtype:
            raise ValueError(f'Unable to select path {path}. The field that has no value.')
          continue
        if current_field.fields:
          if path_part not in current_field.fields:
            raise ValueError(
              f'Unable to select path {path}. ' f'Path part "{path_part}" not found in the dataset.'
            )
          current_field = current_field.fields[path_part]
          continue
        elif current_field.repeated_field:
          if path_part.isdigit():
            raise ValueError(
              f'Unable to select path {path}. Selecting a specific index of '
              'a repeated field is currently not supported.'
            )
          if path_part != PATH_WILDCARD:
            raise ValueError(
              f'Unable to select path {path}. ' f'Path part "{path_part}" should be a wildcard.'
            )
          current_field = current_field.repeated_field
        elif not current_field.dtype:
          raise ValueError(
            f'Unable to select path {path}. '
            f'Path part "{path_part}" is not defined on a primitive value.'
          )

  def _validate_columns(
    self, columns: Sequence[Column], source_schema: Schema, select_schema: Schema
  ) -> None:
    udf_cols = [col for col in columns if col.signal_udf]
    self._validate_udfs(udf_cols, source_schema)
    self._validate_selection(columns, select_schema)

  def _validate_sort_path(self, path: PathTuple, schema: Schema) -> None:
    current_field = Field(fields=schema.fields)
    if path == (ROWID,):
      return
    for path_part in path:
      if path_part == VALUE_KEY:
        if not current_field.dtype:
          raise ValueError(f'Unable to sort by path {path}. The field that has no value.')
        continue
      if current_field.fields:
        if path_part not in current_field.fields:
          raise ValueError(
            f'Unable to sort by path {path}. ' f'Path part "{path_part}" not found in the dataset.'
          )
        current_field = current_field.fields[path_part]
        continue
      elif current_field.repeated_field:
        if path_part.isdigit():
          raise ValueError(
            f'Unable to sort by path {path}. Selecting a specific index of '
            'a repeated field is currently not supported.'
          )
        if path_part != PATH_WILDCARD:
          raise ValueError(
            f'Unable to sort by path {path}. ' f'Path part "{path_part}" should be a wildcard.'
          )
        current_field = current_field.repeated_field
      elif not current_field.dtype:
        raise ValueError(
          f'Unable to sort by path {path}. '
          f'Path part "{path_part}" is not defined on a primitive value.'
        )
    if not current_field.dtype:
      raise ValueError(f'Unable to sort by path {path}. The field has no value.')

  @override
  @functools.cache  # Cache stats for leaf paths since we ask on every dataset page refresh.
  def stats(self, leaf_path: Path) -> StatsResult:
    if not leaf_path:
      raise ValueError('leaf_path must be provided')
    path = normalize_path(leaf_path)
    manifest = self.manifest()
    leaf = manifest.data_schema.get_field(path)
    # Find the inner-most leaf in case this field is repeated.
    while leaf.repeated_field:
      leaf = leaf.repeated_field
      path = (*path, PATH_WILDCARD)

    if not leaf.dtype:
      raise ValueError(f'Leaf "{path}" not found in dataset')

    if leaf.dtype.type == 'map':
      raise ValueError(
        f'Cannot compute stats on a map field "{path}". '
        'Provide a path to a key in that map instead.'
      )

    duckdb_path = self._leaf_path_to_duckdb_path(path, manifest.data_schema)
    inner_select = _select_sql(
      duckdb_path,
      flatten=True,
      unnest=True,
      path=path,
      schema=manifest.data_schema,
      span_from=self._resolve_span(path, manifest),
    )

    # Compute the average length of text fields.
    avg_text_length: Optional[int] = None
    if leaf.dtype in (STRING, STRING_SPAN):
      avg_length_query = f"""
        SELECT avg(length(val))
        FROM (SELECT {inner_select} AS val FROM t) USING SAMPLE {SAMPLE_AVG_TEXT_LENGTH};
      """
      row = self._query(avg_length_query)[0]
      if row[0] is not None:
        avg_text_length = int(row[0])

    total_count_query = f'SELECT count(val) FROM (SELECT {inner_select} as val FROM t)'
    total_count = int(self._query(total_count_query)[0][0])

    # Compute approximate count by sampling the data to avoid OOM.
    if avg_text_length and avg_text_length > MAX_TEXT_LEN_DISTINCT_COUNT:
      # Assume that every text field is unique.
      approx_count_distinct = manifest.num_items
    elif leaf.dtype == BOOLEAN:
      approx_count_distinct = 2
    else:
      sample_size = TOO_MANY_DISTINCT
      approx_count_query = f"""
        SELECT approx_count_distinct(val) as approxCountDistinct
        FROM (SELECT {inner_select} AS val FROM t) USING SAMPLE {sample_size};
      """
      row = self._query(approx_count_query)[0]
      approx_count_distinct = int(row[0])

      # Adjust the counts for the sample size.
      factor = max(1, total_count / sample_size)
      approx_count_distinct = round(approx_count_distinct * factor)

    result = StatsResult(
      path=path,
      total_count=total_count,
      approx_count_distinct=approx_count_distinct,
      avg_text_length=avg_text_length,
    )

    # Compute min/max values for ordinal leafs, without sampling the data.
    if is_ordinal(leaf.dtype):
      min_max_query = f"""
        SELECT MIN(val) AS minVal, MAX(val) AS maxVal
        FROM (SELECT {inner_select} as val FROM t)
        {'WHERE NOT isnan(val)' if is_float(leaf.dtype) else ''}
      """
      row = self._query(min_max_query)[0]
      result.min_val, result.max_val = row

    return result

  @override
  def select_groups(
    self,
    leaf_path: Path,
    filters: Optional[Sequence[FilterLike]] = None,
    sort_by: Optional[GroupsSortBy] = GroupsSortBy.COUNT,
    sort_order: Optional[SortOrder] = SortOrder.DESC,
    limit: Optional[int] = None,
    bins: Optional[Union[Sequence[Bin], Sequence[float]]] = None,
  ) -> SelectGroupsResult:
    if not leaf_path:
      raise ValueError('leaf_path must be provided')
    sort_by = sort_by or GroupsSortBy.COUNT
    sort_order = sort_order or SortOrder.DESC
    path = normalize_path(leaf_path)
    manifest = self.manifest()
    leaf = manifest.data_schema.get_field(path)
    # Find the inner-most leaf in case this field is repeated.
    while leaf.repeated_field:
      leaf = leaf.repeated_field
      path = (*path, PATH_WILDCARD)

    if not leaf.dtype:
      raise ValueError(f'Leaf "{path}" not found in dataset')

    if leaf.dtype.type == 'map':
      raise ValueError(
        f'Cannot compute groups on a map field "{path}". '
        'Provide a path to a key in that map instead.'
      )

    inner_val = 'inner_val'
    outer_select = inner_val
    # Normalize the bins to be `list[Bin]`.
    named_bins = _normalize_bins(bins or leaf.bins)
    stats = self.stats(leaf_path)

    leaf_is_float = is_float(leaf.dtype)
    leaf_is_integer = is_integer(leaf.dtype)
    if not leaf.categorical and (leaf_is_float or leaf_is_integer):
      if named_bins is None:
        # Auto-bin.
        named_bins = _auto_bins(stats, NUM_AUTO_BINS)

      sql_bounds = []
      for label, start, end in named_bins:
        if start is None:
          start = cast(float, "'-Infinity'")
        if end is None:
          end = cast(float, "'Infinity'")
        sql_bounds.append(f"('{label}', {start}, {end})")

      bin_index_col = 'col0'
      bin_min_col = 'col1'
      bin_max_col = 'col2'
      is_nan_filter = f'NOT isnan({inner_val}) AND' if leaf_is_float else ''

      # We cast the field to `double` so binning works for both `float` and `int` fields.
      outer_select = f"""(
        SELECT {bin_index_col} FROM (
          VALUES {', '.join(sql_bounds)}
        ) WHERE {is_nan_filter}
           {inner_val}::DOUBLE >= {bin_min_col} AND {inner_val}::DOUBLE < {bin_max_col}
      )"""
    else:
      if stats.approx_count_distinct >= dataset.TOO_MANY_DISTINCT:
        return SelectGroupsResult(too_many_distinct=True, counts=[], bins=named_bins)

    count_column = GroupsSortBy.COUNT.value
    value_column = GroupsSortBy.VALUE.value

    limit_query = f'LIMIT {limit}' if limit else ''
    duckdb_path = self._leaf_path_to_duckdb_path(path, manifest.data_schema)
    inner_select = _select_sql(
      duckdb_path,
      flatten=True,
      unnest=True,
      path=path,
      schema=manifest.data_schema,
      span_from=self._resolve_span(path, manifest),
    )

    filters, _ = self._normalize_filters(filters, col_aliases={}, udf_aliases={}, manifest=manifest)
    filter_queries = self._create_where(manifest, filters, searches=[])

    where_query = ''
    if filter_queries:
      where_query = f"WHERE {' AND '.join(filter_queries)}"

    query = f"""
      SELECT {outer_select} AS {value_column}, COUNT() AS {count_column}
      FROM (SELECT {inner_select} AS {inner_val} FROM t {where_query})
      GROUP BY {value_column}
      ORDER BY {sort_by.value} {sort_order.value}, {value_column}
      {limit_query}
    """
    df = self._query_df(query)
    counts = list(df.itertuples(index=False, name=None))
    if is_temporal(leaf.dtype):
      # Replace any NaT with None and pd.Timestamp to native datetime objects.
      counts = [(None if pd.isnull(val) else val.to_pydatetime(), count) for val, count in counts]

    return SelectGroupsResult(too_many_distinct=False, counts=counts, bins=named_bins)

  def _topk_udf_to_sort_by(
    self,
    udf_columns: list[Column],
    filters: list[Filter],
    sort_by: list[PathTuple],
    limit: Optional[int],
    sort_order: Optional[SortOrder],
  ) -> Optional[Column]:
    for f in filters:
      # If the user provides a list of row ids, avoid sorting.
      if f.path == (ROWID,):
        if f.op in ('equals', 'in'):
          return None
    if (sort_order != SortOrder.DESC) or (not limit) or (not sort_by):
      return None
    if len(sort_by) < 1:
      return None
    primary_sort_by = sort_by[0]
    udf_cols_to_sort_by = [
      udf_col
      for udf_col in udf_columns
      if udf_col.alias == primary_sort_by[0]
      or _path_contains(_col_destination_path(udf_col), primary_sort_by)
    ]
    if not udf_cols_to_sort_by:
      return None
    udf_col = udf_cols_to_sort_by[0]
    if udf_col.signal_udf and not isinstance(udf_col.signal_udf, VectorSignal):
      return None
    return udf_col

  def _normalize_columns(
    self, columns: Optional[Sequence[ColumnId]], schema: Schema, combine_columns: bool
  ) -> list[Column]:
    """Normalizes the columns to a list of `Column` objects."""
    cols = [column_from_identifier(col) for col in columns or []]
    star_in_cols = any(col.path == (PATH_WILDCARD,) for col in cols)
    if not cols or star_in_cols:
      # Select all columns.
      if not combine_columns:
        # Select all leafs as top-level.
        for path in schema.leafs.keys():
          cols.append(Column(path))
      else:
        cols.extend([Column((name,)) for name in schema.fields.keys() if name != ROWID])

      if star_in_cols:
        cols = [col for col in cols if col.path != (PATH_WILDCARD,)]

    return cols

  def _merge_sorts(
    self,
    search_udfs: list[DuckDBSearchUDF],
    sort_by: Optional[Sequence[Path]],
    sort_order: Optional[SortOrder],
  ) -> list[SortResult]:
    # True when the user has explicitly sorted by the alias of a search UDF (e.g. in ASC order).
    is_explicit_search_sort = False
    for sort_by_path in sort_by or []:
      for search_udf in search_udfs:
        if column_paths_match(sort_by_path, search_udf.output_path):
          is_explicit_search_sort = True
          break

    sort_results: list[SortResult] = []
    if sort_by and not is_explicit_search_sort:
      if not sort_order:
        raise ValueError('`sort_order` is required when `sort_by` is specified.')
      # If the user has explicitly set a sort by, and it's not a search UDF alias, override.
      sort_results = [
        SortResult(path=normalize_path(sort_by), order=sort_order) for sort_by in sort_by if sort_by
      ]
    else:
      search_udfs_with_sort = [search_udf for search_udf in search_udfs if search_udf.sort]
      if search_udfs_with_sort:
        # Override the sort by the last search sort order when the user hasn't provided an
        # explicit sort order.
        last_search_udf = search_udfs_with_sort[-1]
        assert last_search_udf.sort, 'Expected search UDFs with sort to have a sort.'
        udf_sort_path, udf_sort_order = last_search_udf.sort
        sort_results = [
          SortResult(
            path=udf_sort_path,
            order=sort_order or udf_sort_order,
            search_index=len(search_udfs_with_sort) - 1,
          )
        ]

    return sort_results

  @override
  def select_rows(
    self,
    columns: Optional[Sequence[ColumnId]] = None,
    searches: Optional[Sequence[Search]] = None,
    filters: Optional[Sequence[FilterLike]] = None,
    sort_by: Optional[Sequence[Path]] = None,
    sort_order: Optional[SortOrder] = SortOrder.DESC,
    limit: Optional[int] = None,
    offset: Optional[int] = 0,
    task_step_id: Optional[TaskStepId] = None,
    resolve_span: bool = False,
    combine_columns: bool = False,
    user: Optional[UserInfo] = None,
  ) -> SelectRowsResult:
    manifest = self.manifest()
    cols = self._normalize_columns(columns, manifest.data_schema, combine_columns)
    offset = offset or 0
    schema = manifest.data_schema

    self._normalize_searches(searches, manifest)
    search_udfs = self._search_udfs(searches, manifest)

    cols.extend([search_udf.udf for search_udf in search_udfs])
    udf_columns = [col for col in cols if col.signal_udf]
    if combine_columns:
      schema = self.select_rows_schema(
        [Column(path=PATH_WILDCARD)] + udf_columns,
        sort_by,
        sort_order,
        searches,
        combine_columns=True,
      ).data_schema

    self._validate_columns(cols, manifest.data_schema, schema)

    temp_rowid_selected = False
    for col in cols:
      if col.path == (ROWID,):
        temp_rowid_selected = False
        break
      if isinstance(col.signal_udf, VectorSignal):
        temp_rowid_selected = True
    if temp_rowid_selected:
      cols.append(Column(ROWID))

    # Set extra information on any concept signals.
    for udf_col in udf_columns:
      if isinstance(udf_col.signal_udf, (ConceptSignal, ConceptLabelsSignal)):
        # Concept are access controlled so we tell it about the user.
        udf_col.signal_udf.set_user(user)

    # Decide on the exact sorting order.
    sort_results = self._merge_sorts(search_udfs, sort_by, sort_order)
    sort_by = cast(
      list[PathTuple], [(sort.alias,) if sort.alias else sort.path for sort in sort_results]
    )
    # Choose the first sort order as we only support a single sort order for now.
    sort_order = sort_results[0].order if sort_results else None

    col_aliases: dict[str, PathTuple] = {col.alias: col.path for col in cols if col.alias}
    udf_aliases: dict[str, PathTuple] = {
      col.alias: col.path for col in cols if col.signal_udf and col.alias
    }
    path_to_udf_col_name: dict[PathTuple, str] = {}
    for col in cols:
      if col.signal_udf:
        alias = col.alias or _unique_alias(col)
        dest_path = _col_destination_path(col)
        path_to_udf_col_name[dest_path] = alias

    # Filtering and searching.
    where_query = ''
    filters, udf_filters = self._normalize_filters(filters, col_aliases, udf_aliases, manifest)
    filter_queries = self._create_where(manifest, filters, searches)
    if filter_queries:
      where_query = f"WHERE {' AND '.join(filter_queries)}"

    total_num_rows = manifest.num_items
    con = self.con.cursor()

    topk_udf_col = self._topk_udf_to_sort_by(udf_columns, filters, sort_by, limit, sort_order)
    if topk_udf_col:
      rowids: Optional[list[str]] = None
      if where_query:
        # If there are filters, we need to send rowids to the top k query.
        df = con.execute(f'SELECT {ROWID} FROM t {where_query}').df()
        total_num_rows = len(df)
        rowids = [rowid for rowid in df[ROWID]]

      if rowids is not None and len(rowids) == 0:
        where_query = 'WHERE false'
      else:
        topk_signal = cast(VectorSignal, topk_udf_col.signal_udf)
        # The input is an embedding.
        vector_index = self._get_vector_db_index(topk_signal.embedding, topk_udf_col.path)
        k = (limit or 0) + offset
        path_id = f'{self.namespace}/{self.dataset_name}:{topk_udf_col.path}'
        with DebugTimer(
          f'Computing topk on {path_id} with embedding "{topk_signal.embedding}" '
          f'and vector store "{vector_index._vector_store.name}"'
        ):
          topk = topk_signal.vector_compute_topk(k, vector_index, rowids)
        topk_rowids = list(dict.fromkeys([cast(str, rowid) for (rowid, *_), _ in topk]))
        # Update the offset to account for the number of unique rowids.
        offset = len(dict.fromkeys([cast(str, rowid) for (rowid, *_), _ in topk[:offset]]))

        # Ignore all the other filters and filter DuckDB results only by the top k rowids.
        rowid_filter = Filter(path=(ROWID,), op='in', value=topk_rowids)
        filter_query = self._create_where(manifest, [rowid_filter])[0]
        where_query = f'WHERE {filter_query}'

    # Map a final column name to a list of temporary namespaced column names that need to be merged.
    columns_to_merge: dict[str, dict[str, Column]] = {}
    temp_column_to_offset_column: dict[str, tuple[str, Field]] = {}
    select_queries: list[str] = []

    for column in cols:
      path = column.path
      # If the signal is vector-based, we don't need to select the actual data, just the rowids
      # plus an arbitrarily nested array of `None`s`.
      empty = bool(column.signal_udf and schema.get_field(path).dtype == EMBEDDING)

      select_sqls: list[str] = []
      final_col_name = column.alias or _unique_alias(column)
      if final_col_name not in columns_to_merge:
        columns_to_merge[final_col_name] = {}

      duckdb_paths = self._column_to_duckdb_paths(column, schema, combine_columns)
      span_from = self._resolve_span(path, manifest) if resolve_span or column.signal_udf else None

      for parquet_id, duckdb_path in duckdb_paths:
        sql = _select_sql(
          duckdb_path,
          flatten=False,
          unnest=False,
          path=path,
          schema=schema,
          empty=empty,
          span_from=span_from,
        )
        temp_column_name = (
          final_col_name if len(duckdb_paths) == 1 else f'{final_col_name}/{parquet_id}'
        )
        select_sqls.append(f'{sql} AS {_escape_string_literal(temp_column_name)}')
        columns_to_merge[final_col_name][temp_column_name] = column

        if column.signal_udf and span_from and _schema_has_spans(column.signal_udf.fields()):
          sql = _select_sql(
            duckdb_path,
            flatten=False,
            unnest=False,
            path=path,
            schema=schema,
            empty=empty,
            span_from=None,
          )
          temp_offset_column_name = f'{temp_column_name}/offset'
          temp_offset_column_name = temp_offset_column_name.replace("'", "\\'")
          select_sqls.append(f'{sql} AS {_escape_string_literal(temp_offset_column_name)}')
          temp_column_to_offset_column[temp_column_name] = (
            temp_offset_column_name,
            column.signal_udf.fields(),
          )

      # `select_sqls` can be empty if this column points to a path that will be created by a UDF.
      if select_sqls:
        select_queries.append(', '.join(select_sqls))

    sort_sql_before_udf: list[str] = []
    sort_sql_after_udf: list[str] = []

    for path in sort_by:
      # We only allow sorting by nodes with a value.
      first_subpath = str(path[0])
      rest_of_path = path[1:]
      signal_alias = '.'.join(map(str, path))

      udf_path = _path_to_udf_duckdb_path(path, path_to_udf_col_name)
      if not udf_path:
        # Re-route the path if it starts with an alias by pointing it to the actual path.
        if first_subpath in col_aliases:
          path = (*col_aliases[first_subpath], *rest_of_path)
        self._validate_sort_path(path, schema)
        sql_path = self._leaf_path_to_duckdb_path(path, schema)
      else:
        sql_path = udf_path

      sort_sql = _select_sql(sql_path, flatten=True, unnest=False, path=path, schema=schema)
      has_repeated_field = any(subpath == PATH_WILDCARD for subpath in sql_path)
      if has_repeated_field:
        sort_sql = (
          f'list_min({sort_sql})' if sort_order == SortOrder.ASC else f'list_max({sort_sql})'
        )

      # Separate sort columns into two groups: those that need to be sorted before and after UDFs.
      if udf_path:
        sort_sql_after_udf.append(sort_sql)
      else:
        sort_sql_before_udf.append(sort_sql)

    order_query = ''
    if sort_sql_before_udf:
      order_query = (
        f'ORDER BY {", ".join(sort_sql_before_udf)} ' f'{cast(SortOrder, sort_order).value}'
      )

    limit_query = ''
    if limit:
      if topk_udf_col:
        limit_query = f'LIMIT {limit + offset}'
      elif sort_sql_after_udf:
        limit_query = ''
      else:
        limit_query = f'LIMIT {limit} OFFSET {offset}'

    if not topk_udf_col and where_query:
      total_num_rows = cast(tuple, con.execute(f'SELECT COUNT(*) FROM t {where_query}').fetchone())[
        0
      ]

    # Fetch the data from DuckDB.
    df = con.execute(
      f"""
      SELECT {', '.join(select_queries)} FROM t
      {where_query}
      {order_query}
      {limit_query}
    """
    ).df()
    df = _replace_nan_with_none(df)

    # Run UDFs on the transformed columns.
    for udf_col in udf_columns:
      signal = cast(Signal, udf_col.signal_udf)
      signal_alias = udf_col.alias or _unique_alias(udf_col)
      temp_signal_cols = columns_to_merge[signal_alias]
      if len(temp_signal_cols) != 1:
        raise ValueError(
          f'Unable to compute signal {signal.name}. Signal UDFs only operate on leafs, but got '
          f'{len(temp_signal_cols)} underlying columns that contain data related to {udf_col.path}.'
        )
      signal_column = list(temp_signal_cols.keys())[0]
      input = df[signal_column]

      path_id = f'{self.namespace}/{self.dataset_name}:{udf_col.path}'
      with DebugTimer(f'Computing signal "{signal.name}" on {path_id}'):
        signal.setup()

        step_description = f'Computing {signal.key()} on {path_id}'

        if isinstance(signal, VectorSignal):
          embedding_signal = signal
          vector_store = self._get_vector_db_index(embedding_signal.embedding, udf_col.path)
          flat_keys = list(flatten_keys(df[ROWID], input))
          signal_out = sparse_to_dense_compute(
            iter(flat_keys), lambda keys: embedding_signal.vector_compute(keys, vector_store)
          )
          # Add progress.
          if task_step_id is not None:
            signal_out = progress(
              signal_out,
              task_step_id=task_step_id,
              estimated_len=len(flat_keys),
              step_description=step_description,
            )
          df[signal_column] = list(deep_unflatten(signal_out, input))
        else:
          num_rich_data = count_primitives(input)
          flat_input = cast(Iterator[Optional[RichData]], deep_flatten(input))
          signal_out = sparse_to_dense_compute(
            flat_input, lambda x: signal.compute(cast(Iterable[RichData], x))
          )
          # Add progress.
          if task_step_id is not None:
            signal_out = progress(
              signal_out,
              task_step_id=task_step_id,
              estimated_len=num_rich_data,
              step_description=step_description,
            )
          signal_out_list = list(signal_out)
          if signal_column in temp_column_to_offset_column:
            offset_column_name, field = temp_column_to_offset_column[signal_column]
            nested_spans: Iterable[Item] = df[offset_column_name]
            flat_spans = deep_flatten(nested_spans)
            for span, item in zip(flat_spans, signal_out_list):
              _offset_any_span(cast(int, span[SPAN_KEY][TEXT_SPAN_START_FEATURE]), item, field)

          if len(signal_out_list) != num_rich_data:
            raise ValueError(
              f'The signal generated {len(signal_out_list)} values but the input data had '
              f"{num_rich_data} values. This means the signal either didn't generate a "
              '"None" for a sparse output, or generated too many items.'
            )

          df[signal_column] = list(deep_unflatten(signal_out_list, input))

        signal.teardown()

    if not df.empty and (udf_filters or sort_sql_after_udf):
      # Re-upload the udf outputs to duckdb so we can filter/sort on them.
      rel = con.from_df(df)

      if udf_filters:
        udf_filter_queries = self._create_where(manifest, udf_filters)
        if udf_filter_queries:
          rel = rel.filter(' AND '.join(udf_filter_queries))
          total_num_rows = cast(tuple, rel.count('*').fetchone())[0]  # type: ignore

      if sort_sql_after_udf:
        if not sort_order:
          raise ValueError('`sort_order` is required when `sort_by` is specified.')
        rel = rel.order(f'{", ".join(sort_sql_after_udf)} {sort_order.value}')

      if limit:
        rel = rel.limit(limit, offset)

      df = _replace_nan_with_none(rel.df())

    if temp_rowid_selected:
      del df[ROWID]
      del columns_to_merge[ROWID]

    if combine_columns:
      all_columns: dict[str, Column] = {}
      for col_dict in columns_to_merge.values():
        all_columns.update(col_dict)
      columns_to_merge = {'*': all_columns}

    for offset_column, _ in temp_column_to_offset_column.values():
      del df[offset_column]

    for final_col_name, temp_columns in columns_to_merge.items():
      for temp_col_name, column in temp_columns.items():
        if combine_columns:
          dest_path = _col_destination_path(column)
          spec = _split_path_into_subpaths_of_lists(dest_path)
          df[temp_col_name] = list(wrap_in_dicts(df[temp_col_name], spec))

        # If the temp col name is the same as the final name, we can skip merging. This happens when
        # we select a source leaf column.
        if temp_col_name == final_col_name:
          continue

        if final_col_name not in df:
          df[final_col_name] = df[temp_col_name]
        else:
          df[final_col_name] = merge_series(df[final_col_name], df[temp_col_name])
        del df[temp_col_name]

    con.close()

    if combine_columns:
      # Since we aliased every column to `*`, the object will have only '*' as the key. We need to
      # elevate the all the columns under '*'.
      df = pd.DataFrame.from_records(df['*'])

    return SelectRowsResult(df, total_num_rows)

  @override
  def select_rows_schema(
    self,
    columns: Optional[Sequence[ColumnId]] = None,
    sort_by: Optional[Sequence[Path]] = None,
    sort_order: Optional[SortOrder] = None,
    searches: Optional[Sequence[Search]] = None,
    combine_columns: bool = False,
  ) -> SelectRowsSchemaResult:
    """Returns the schema of the result of `select_rows` above with the same arguments."""
    if not combine_columns:
      raise NotImplementedError(
        'select_rows_schema with combine_columns=False is not yet supported.'
      )
    manifest = self.manifest()
    cols = self._normalize_columns(columns, manifest.data_schema, combine_columns)

    self._normalize_searches(searches, manifest)
    search_udfs = self._search_udfs(searches, manifest)
    cols.extend([search_udf.udf for search_udf in search_udfs])

    udfs: list[SelectRowsSchemaUDF] = []
    col_schemas: list[Schema] = []
    for col in cols:
      dest_path = _col_destination_path(col)
      if col.signal_udf:
        udfs.append(SelectRowsSchemaUDF(path=dest_path, alias=col.alias))
        field = col.signal_udf.fields()
        field.signal = col.signal_udf.model_dump()
      elif manifest.data_schema.has_field(dest_path):
        field = manifest.data_schema.get_field(dest_path)
      else:
        # This column might refer to an output of a udf. We postpone validation to later.
        continue
      col_schemas.append(_make_schema_from_path(dest_path, field))

    sort_results = self._merge_sorts(search_udfs, sort_by, sort_order)

    search_results = [
      SearchResultInfo(search_path=search_udf.search_path, result_path=search_udf.output_path)
      for search_udf in search_udfs
    ]

    new_schema = merge_schemas(col_schemas)

    # Now that we have the new schema, we can validate all the column selections.
    self._validate_columns(cols, manifest.data_schema, new_schema)

    return SelectRowsSchemaResult(
      data_schema=new_schema, udfs=udfs, search_results=search_results, sorts=sort_results or None
    )

  @override
  def add_labels(
    self,
    name: str,
    row_ids: Optional[Sequence[str]] = None,
    searches: Optional[Sequence[Search]] = None,
    filters: Optional[Sequence[FilterLike]] = None,
    value: Optional[str] = 'true',
  ) -> int:
    created = datetime.now()

    # If filters and searches are defined with row_ids, add this as a filter.
    if row_ids and (searches or filters):
      filters = list(filters) if filters else []
      filters.append(Filter(path=(ROWID,), op='in', value=list(row_ids)))

    insert_row_ids: Iterable[str]
    if row_ids and not searches and not filters:
      insert_row_ids = row_ids
    else:
      insert_row_ids = (
        row[ROWID] for row in self.select_rows(columns=[ROWID], searches=searches, filters=filters)
      )

    # Check if the label file exists.
    labels_filepath = get_labels_sqlite_filename(self.dataset_path, name)

    if labels_filepath not in self._label_file_lock:
      self._label_file_lock[labels_filepath] = threading.Lock()

    with self._label_file_lock[labels_filepath]:
      # We don't cache sqlite connections as they cannot be shared across threads.
      sqlite_con = sqlite3.connect(labels_filepath)
      sqlite_cur = sqlite_con.cursor()

      # Create the table if it doesn't exist.
      sqlite_cur.execute(
        f"""
        CREATE TABLE IF NOT EXISTS "{name}" (
          {ROWID} VARCHAR NOT NULL PRIMARY KEY,
          label VARCHAR NOT NULL,
          created DATETIME)
      """
      )

      num_labels = 0
      for row_id in insert_row_ids:
        # We use ON CONFLICT to resolve the same row UUID being labeled again. In this case, we
        # overwrite the existing label with the new label.
        sqlite_cur.execute(
          f"""
            INSERT INTO "{name}" VALUES (?, ?, ?)
            ON CONFLICT({ROWID}) DO UPDATE SET label=excluded.label;
          """,
          (row_id, value, created.isoformat()),
        )
        num_labels += 1
      sqlite_con.commit()
      sqlite_con.close()

    return num_labels

  @override
  def get_label_names(self) -> list[str]:
    self.manifest()
    return list(self._label_schemas.keys())

  @override
  def remove_labels(
    self,
    name: str,
    row_ids: Optional[Sequence[str]] = None,
    searches: Optional[Sequence[Search]] = None,
    filters: Optional[Sequence[FilterLike]] = None,
  ) -> int:
    # Check if the label file exists.
    labels_filepath = get_labels_sqlite_filename(self.dataset_path, name)

    if not os.path.exists(labels_filepath):
      raise ValueError(f'Label with name "{name}" does not exist.')

    # If filters and searches are defined with row_ids, add this as a filter.
    if row_ids and (searches or filters):
      filters = list(filters) if filters else []
      filters.append(Filter(path=(ROWID,), op='in', value=list(row_ids)))

    remove_row_ids: Sequence[str]
    if row_ids and not searches and not filters:
      remove_row_ids = row_ids
    else:
      remove_row_ids = [
        row[ROWID] for row in self.select_rows(columns=[ROWID], searches=searches, filters=filters)
      ]

    if labels_filepath not in self._label_file_lock:
      self._label_file_lock[labels_filepath] = threading.Lock()

    with self._label_file_lock[labels_filepath]:
      with closing(sqlite3.connect(labels_filepath)) as conn:
        conn.executemany(
          f"""
            DELETE FROM "{name}"
            WHERE {ROWID} = ?
          """,
          [(x,) for x in remove_row_ids],
        )
        conn.commit()
        count = conn.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0]
        if count == 0:
          delete_file(labels_filepath)

    return len(remove_row_ids)

  @override
  def media(self, item_id: str, leaf_path: Path) -> MediaResult:
    raise NotImplementedError('Media is not yet supported for the DuckDB implementation.')

  def _resolve_span(
    self, span_path: PathTuple, manifest: DatasetManifest
  ) -> Optional[tuple[Union[SignalManifest, MapManifest], PathTuple]]:
    schema = manifest.data_schema
    leafs = schema.leafs
    is_span = span_path in leafs and leafs[span_path].dtype == STRING_SPAN
    if not is_span:
      return None

    # Find the manifest that contains the span path.
    manifests: list[Union[SignalManifest, MapManifest]] = (
      self._signal_manifests + self._map_manifests
    )
    span_manifest = next(
      filter(
        lambda s: schema_contains_path(s.data_schema, span_path),
        manifests,
      )
    )

    # Find the original text, which is the closest parent of `path` above the signal root.
    text_path: PathTuple
    for i in reversed(range(len(span_path))):
      sub_path = span_path[:i]
      sub_field = schema.get_field(sub_path)
      if sub_field.signal is not None or sub_field.map is not None:
        # Skip the signal name at the end to get the source path that was enriched.
        text_path = sub_path[:-1]
        return (span_manifest, text_path)

    raise ValueError('Cannot find the source path for the enriched path: {path}')

  def _leaf_path_to_duckdb_path(self, leaf_path: PathTuple, schema: Schema) -> PathTuple:
    [(_, duckdb_path), *rest] = self._column_to_duckdb_paths(
      Column(leaf_path), schema, combine_columns=False
    )
    return duckdb_path

  def _column_to_duckdb_paths(
    self, column: Column, schema: Schema, combine_columns: bool
  ) -> list[tuple[str, PathTuple]]:
    path = column.path
    if path[0] in self._label_schemas:
      # This is a label column if it exists in label schemas.
      return [(path[0], path)]

    is_petal = schema.get_field(path).dtype is not None

    # NOTE: The order of this array matters as we check the source and map manifests for fields
    # before reading signal manifests, via source_or_map_has_path.
    parquet_manifests: list[Union[SourceManifest, SignalManifest, MapManifest]] = [
      self._source_manifest,
      *self._map_manifests,
      *self._signal_manifests,
    ]
    duckdb_paths: list[tuple[str, PathTuple]] = []

    if path == (ROWID,):
      return [('source', path)]

    for m in parquet_manifests:
      if not m.files:
        continue
      # Skip this parquet file if it doesn't contain the path.
      # if not schema_contains_path(m.data_schema, path):
      #   continue
      if not m.data_schema.has_field(path):
        continue

      # If the path is a petal, and the manifest owns its petal value, then this is the relevant
      # manifest.
      field = m.data_schema.get_field(path)
      manifest_has_petal_value = field.dtype is not None
      if not manifest_has_petal_value and is_petal and not combine_columns:
        continue

      # Skip this parquet file if the path doesn't have a dtype.
      if column.signal_udf and not m.data_schema.get_field(path).dtype:
        continue

      duckdb_path = path
      parquet_id = 'source'

      if isinstance(m, SignalManifest):
        duckdb_path = (m.parquet_id, *path[1:])
        parquet_id = m.parquet_id
      elif isinstance(m, MapManifest):
        duckdb_path = (m.parquet_id, *path[1:])
        parquet_id = m.parquet_id

      duckdb_paths.append((parquet_id, duckdb_path))

    if not duckdb_paths:
      # This path is probably a result of a udf. Make sure the result schema contains it.
      if not schema.has_field(path):
        raise ValueError(
          f'Invalid path "{path}": No manifest contains path. Valid paths: '
          f'{list(schema.leafs.keys())}'
        )

    return duckdb_paths

  def _normalize_filters(
    self,
    filter_likes: Optional[Sequence[FilterLike]],
    col_aliases: dict[str, PathTuple],
    udf_aliases: dict[str, PathTuple],
    manifest: DatasetManifest,
  ) -> tuple[list[Filter], list[Filter]]:
    """Normalize `FilterLike` to `Filter` and split into filters on source and filters on UDFs."""
    filter_likes = filter_likes or []
    filters: list[Filter] = []
    udf_filters: list[Filter] = []

    for filter in filter_likes:
      # Normalize `FilterLike` to `Filter`.
      if not isinstance(filter, Filter):
        if len(filter) == 3:
          path, op, value = filter  # type: ignore
        elif len(filter) == 2:
          path, op = filter  # type: ignore
          value = None
        else:
          raise ValueError(f'Invalid filter: {filter}. Must be a tuple with 2 or 3 elements.')
        filter = Filter(path=normalize_path(path), op=op, value=value)

      if str(filter.path[0]) in udf_aliases:
        udf_filters.append(filter)
      else:
        filters.append(filter)

    self._validate_filters(filters, col_aliases, manifest)
    return filters, udf_filters

  def _normalize_searches(
    self, searches: Optional[Sequence[Search]], manifest: DatasetManifest
  ) -> None:
    """Validate searches."""
    if not searches:
      return

  def _search_udfs(
    self, searches: Optional[Sequence[Search]], manifest: DatasetManifest
  ) -> list[DuckDBSearchUDF]:
    searches = searches or []
    """Create a UDF for each search for finding the location of the text with spans."""
    search_udfs: list[DuckDBSearchUDF] = []
    for search in searches:
      search_path = normalize_path(search.path)
      if search.type == 'keyword':
        udf = Column(path=search_path, signal_udf=SubstringSignal(query=search.query))
        search_udfs.append(
          DuckDBSearchUDF(
            udf=udf,
            search_path=search_path,
            output_path=(*_col_destination_path(udf), PATH_WILDCARD),
          )
        )
      elif search.type == 'metadata':
        udf = Column(
          path=search_path, signal_udf=FilterMaskSignal(op=search.op, value=search.value)
        )
        search_udfs.append(
          DuckDBSearchUDF(udf=udf, search_path=search_path, output_path=_col_destination_path(udf))
        )
      elif search.type == 'semantic' or search.type == 'concept':
        embedding = search.embedding
        if not embedding:
          raise ValueError(f'Please provide an embedding for semantic search. Got search: {search}')

        try:
          manifest.data_schema.get_field((*search_path, embedding))
        except Exception as e:
          raise ValueError(
            f'Embedding {embedding} has not been computed. '
            f'Please compute the embedding index before issuing a {search.type} query.'
          ) from e

        search_signal: Optional[Signal] = None
        if search.type == 'semantic':
          search_signal = SemanticSimilaritySignal(
            query=search.query, embedding=search.embedding, query_type=search.query_type
          )
        elif search.type == 'concept':
          search_signal = ConceptSignal(
            namespace=search.concept_namespace,
            concept_name=search.concept_name,
            embedding=search.embedding,
          )

          # Add the label UDF.
          concept_labels_signal = ConceptLabelsSignal(
            namespace=search.concept_namespace, concept_name=search.concept_name
          )
          concept_labels_udf = Column(path=search_path, signal_udf=concept_labels_signal)
          search_udfs.append(
            DuckDBSearchUDF(
              udf=concept_labels_udf,
              search_path=search_path,
              output_path=_col_destination_path(concept_labels_udf),
              sort=None,
            )
          )

        udf = Column(path=search_path, signal_udf=search_signal)

        output_path = _col_destination_path(udf)
        search_udfs.append(
          DuckDBSearchUDF(
            udf=udf,
            search_path=search_path,
            output_path=_col_destination_path(udf),
            sort=((*output_path, PATH_WILDCARD, 'score'), SortOrder.DESC),
          )
        )
      else:
        raise ValueError(f'Unknown search operator {search.type}.')

    return search_udfs

  def _create_where(
    self,
    manifest: DatasetManifest,
    filters: list[Filter],
    searches: Optional[Sequence[Search]] = [],
  ) -> list[str]:
    if not filters and not searches:
      return []
    searches = searches or []
    sql_filter_queries: list[str] = []

    # Add search where queries.
    for search in searches:
      search_path = normalize_path(search.path)
      duckdb_path = self._leaf_path_to_duckdb_path(search_path, manifest.data_schema)
      select_str = _select_sql(
        duckdb_path, flatten=False, unnest=False, path=search_path, schema=manifest.data_schema
      )
      if search.type == 'keyword':
        sql_op = 'ILIKE'
        query_val = _escape_like_value(search.query)
        sql_filter_queries.append(f'{select_str} {sql_op} {query_val}')
      elif search.type == 'semantic' or search.type == 'concept':
        # Semantic search and concepts don't yet filter.
        continue
      elif search.type == 'metadata':
        # Make a regular filter query.
        filter = Filter(path=search_path, op=search.op, value=search.value)
        filters.append(filter)
      else:
        raise ValueError(f'Unknown search operator {search.type}.')

    # Add filter where queries.
    for f in filters:
      duckdb_path = self._leaf_path_to_duckdb_path(f.path, manifest.data_schema)
      select_str = _select_sql(
        duckdb_path,
        flatten=True,
        unnest=False,
        path=f.path,
        schema=manifest.data_schema,
        span_from=self._resolve_span(f.path, manifest),
      )
      is_array = any(subpath == PATH_WILDCARD for subpath in f.path)
      if len(f.path) > 1 and manifest.data_schema.has_field(f.path[:-1]):
        # Accessing a key in a map always returns an array.
        parent_field = manifest.data_schema.get_field(f.path[:-1])
        if parent_field.dtype and parent_field.dtype.type == 'map':
          is_array = True

      nan_filter = ''
      field = manifest.data_schema.get_field(f.path)
      filter_nans = field.dtype and is_float(field.dtype)

      if f.op in BINARY_OPS:
        sql_op = BINARY_OP_TO_SQL[cast(BinaryOp, f.op)]
        filter_val = cast(FeatureValue, f.value)
        if isinstance(filter_val, str):
          filter_val = _escape_string_literal(filter_val)
        elif isinstance(filter_val, bytes):
          filter_val = _bytes_to_blob_literal(filter_val)
        else:
          filter_val = str(filter_val)
        if is_array:
          nan_filter = 'NOT isnan(x) AND' if filter_nans else ''
          filter_query = (
            f'len(list_filter({select_str}, ' f'x -> {nan_filter} x {sql_op} {filter_val})) > 0'
          )
        else:
          nan_filter = f'NOT isnan({select_str}) AND' if filter_nans else ''
          filter_query = f'{nan_filter} {select_str} {sql_op} {filter_val}'
      elif f.op in UNARY_OPS:
        if f.op == 'exists':
          filter_query = (
            f'ifnull(len({select_str}), 0) > 0' if is_array else f'{select_str} IS NOT NULL'
          )
        elif f.op == 'not_exists':
          filter_query = (
            f'ifnull(len({select_str}), 0) = 0' if is_array else f'{select_str} IS NULL'
          )
        else:
          raise ValueError(f'Unary op: {f.op} is not yet supported')
      elif f.op in LIST_OPS:
        if f.op == 'in':
          filter_list_val = cast(FeatureListValue, f.value)
          if not isinstance(filter_list_val, list):
            raise ValueError('filter with array value can only use the IN comparison')
          wrapped_filter_val = [f"'{part}'" for part in filter_list_val]
          filter_val = f'({", ".join(wrapped_filter_val)})'
          filter_query = f'{select_str} IN {filter_val}'
        else:
          raise ValueError(f'List op: {f.op} is not yet supported')
      else:
        raise ValueError(f'Invalid filter op: {f.op}')
      sql_filter_queries.append(filter_query)
    return sql_filter_queries

  def _execute(self, query: str) -> duckdb.DuckDBPyConnection:
    """Execute a query in duckdb."""
    # FastAPI is multi-threaded so we have to create a thread-specific connection cursor to allow
    # these queries to be thread-safe.
    local_con = self.con.cursor()
    if not env('DEBUG', False):
      return local_con.execute(query)

    # Debug mode.
    log('Executing:')
    log(query)
    with DebugTimer('Query'):
      return local_con.execute(query)

  def _query(self, query: str) -> list[tuple]:
    result = self._execute(query)
    rows = result.fetchall()
    result.close()
    return rows

  def _query_df(self, query: str) -> pd.DataFrame:
    """Execute a query that returns a data frame."""
    result = self._execute(query)
    df = _replace_nan_with_none(result.df())
    result.close()
    return df

  def _path_to_col(self, path: Path, quote_each_part: bool = True) -> str:
    """Convert a path to a column name."""
    if isinstance(path, str):
      path = (path,)
    return '.'.join(
      [
        f'{_escape_col_name(path_comp)}' if quote_each_part else str(path_comp)
        for path_comp in path
      ]
    )

  def _get_selection(
    self,
    columns: Optional[Sequence[ColumnId]] = None,
    filters: Optional[Sequence[FilterLike]] = None,
    include_labels: Optional[Sequence[str]] = None,
    exclude_labels: Optional[Sequence[str]] = None,
  ) -> str:
    """Get the selection clause for download a dataset."""
    manifest = self.manifest()
    cols = self._normalize_columns(columns, manifest.data_schema, combine_columns=False)
    schema = manifest.data_schema
    self._validate_columns(cols, manifest.data_schema, schema)

    filters = list(filters or [])
    include_labels = include_labels or []
    exclude_labels = exclude_labels or []
    include_labels_query = ''

    if include_labels:
      include_filters = [Filter(path=(label,), op='exists') for label in include_labels]
      include_labels_query = f"({' OR '.join(self._create_where(manifest, include_filters))})"

    for label in exclude_labels:
      filters.append(Filter(path=(label,), op='not_exists'))

    where_query = ''
    filters, _ = self._normalize_filters(filters, col_aliases={}, udf_aliases={}, manifest=manifest)
    filter_queries = self._create_where(manifest, filters)
    if include_labels_query:
      filter_queries.append(include_labels_query)
    if filter_queries:
      where_query = f"WHERE {' AND '.join(filter_queries)}"

    select_queries: list[str] = []
    for column in cols:
      col_name = column.alias or _unique_alias(column)
      duckdb_paths = self._column_to_duckdb_paths(column, schema, combine_columns=False)
      if not duckdb_paths:
        raise ValueError(f'Cannot download path {column.path} which does not exist in the dataset.')
      if len(duckdb_paths) > 1:
        raise ValueError(
          f'Cannot download path {column.path} which spans multiple parquet files: {duckdb_paths}'
        )
      _, duckdb_path = duckdb_paths[0]
      sql = _select_sql(duckdb_path, flatten=False, unnest=False, path=column.path, schema=schema)
      select_queries.append(f'{sql} AS {_escape_string_literal(col_name)}')
    selection = ', '.join(select_queries)
    return f'SELECT {selection} FROM t {where_query}'

  @override
  def map(
    self,
    map_fn: MapFn,
    output_column: Optional[str] = None,
    nest_under: Optional[Path] = None,
    overwrite: bool = False,
    combine_columns: bool = False,
    resolve_span: bool = False,
    num_jobs: int = 1,
  ) -> Iterable[Item]:
    is_tmp_output = output_column is None

    manifest = self.manifest()

    # Validate output_column and nest_under.
    if nest_under is not None:
      nest_under = normalize_path(nest_under)
      if output_column is None:
        raise ValueError('When using `nest_under`, you must specify an output column name.')

      # Make sure nest_under does not contain any repeated values.
      for path_part in nest_under:
        if path_part == PATH_WILDCARD:
          raise ValueError('Nesting map outputs under a repeated field is not yet supported.')

      if not manifest.data_schema.has_field(nest_under):
        raise ValueError(f'The `nest_under` column {nest_under} does not exist.')

    # If the user didn't provide an output_column, we make a temporary one so that we can store the
    # output JSON objects in the cache, represented in the right hierarchy.
    if output_column is None:
      output_column = cast(str, getattr(map_fn, 'name', None)) or map_fn.__name__

    if nest_under is not None:
      output_path = (*nest_under, output_column)
    else:
      output_path = (output_column,)

    parquet_filepath: Optional[str] = None
    if not is_tmp_output:
      if manifest.data_schema.has_field(output_path):
        if overwrite:
          field = manifest.data_schema.get_field(output_path)
          if field.map is None:
            raise ValueError(f'{output_path} is not a map column so it cannot be overwritten.')
          # Delete the parquet file and map manifest.
          assert output_column is not None
          parquet_filepath = os.path.join(
            self.dataset_path, get_parquet_filename(output_column, shard_index=0, num_shards=1)
          )
          if os.path.exists(parquet_filepath):
            delete_file(parquet_filepath)

          map_manifest_filepath = os.path.join(
            self.dataset_path, f'{output_column}.{MAP_MANIFEST_SUFFIX}'
          )
          if os.path.exists(map_manifest_filepath):
            delete_file(map_manifest_filepath)

        else:
          raise ValueError(
            f'Cannot map to path "{output_column}" which already exists in the dataset. '
            'Use overwrite=True to overwrite the column.'
          )

    num_jobs = get_task_manager().get_num_workers() if num_jobs == -1 else num_jobs

    task_ids = []
    jsonl_cache_filepaths: list[str] = []
    for i in range(num_jobs):
      output_col_desc_suffix = f' to "{output_column}"' if output_column else ''
      task_id = get_task_manager().task_id(
        name=f'[{self.namespace}/{self.dataset_name}][shard {i}/{num_jobs}] map '
        f'"{map_fn.__name__}"{output_col_desc_suffix}',
      )
      jsonl_cache_filepath = _jsonl_cache_filepath(
        namespace=self.namespace,
        dataset_name=self.dataset_name,
        key=output_path,
        project_dir=self.project_dir,
        is_temporary=is_tmp_output,
        shard_id=i,
        shard_count=num_jobs,
      )
      get_task_manager().execute(
        task_id,
        self._map_worker,
        map_fn,
        output_path,
        jsonl_cache_filepath,
        i,
        num_jobs,
        overwrite,
        combine_columns,
        resolve_span,
        (task_id, 0),
      )
      task_ids.append(task_id)
      jsonl_cache_filepaths.append(jsonl_cache_filepath)

    # Wait for the tasks to finish before reading the outputs.
    get_task_manager().wait(task_ids)

    reader, map_schema, parquet_filepath = self._reshard_cache(
      output_path=output_path,
      jsonl_cache_filepaths=jsonl_cache_filepaths,
      is_tmp_output=is_tmp_output,
    )

    if not is_tmp_output:
      assert parquet_filepath is not None

      map_field_root = map_schema.get_field(output_path)

      map_field_root.map = MapInfo(
        fn_name=map_fn.__name__, fn_source=inspect.getsource(map_fn), date_created=datetime.now()
      )

      parquet_dir = os.path.dirname(parquet_filepath)
      map_manifest_filepath = os.path.join(parquet_dir, f'{output_column}.{MAP_MANIFEST_SUFFIX}')
      parquet_filename = os.path.basename(parquet_filepath)
      map_manifest = MapManifest(
        files=[parquet_filename],
        data_schema=map_schema,
        parquet_id=get_map_parquet_id(output_path),
        py_version=metadata.version('lilac'),
      )
      with open_file(map_manifest_filepath, 'w') as f:
        f.write(map_manifest.model_dump_json(exclude_none=True, indent=2))

      parquet_filepath = os.path.join(self.dataset_path, parquet_filepath)
      log(f'Wrote map output to {parquet_filepath}')

    return DuckDBMapOutput(pyarrow_reader=reader, output_column=output_column)

  def _map_worker(
    self,
    map_fn: MapFn,
    output_path: PathTuple,
    jsonl_cache_filepath: str,
    job_id: int,
    job_count: int,
    overwrite: bool = False,
    combine_columns: bool = False,
    resolve_span: bool = False,
    task_step_id: Optional[TaskStepId] = None,
  ) -> None:
    def _map_iterable(items: Iterable[RichData]) -> Iterable[Optional[Item]]:
      for item in items:
        yield map_fn(item, job_id=job_id)

    self._compute_disk_cached(
      _map_iterable,
      output_path=output_path,
      jsonl_cache_filepath=jsonl_cache_filepath,
      overwrite=overwrite,
      combine_columns=combine_columns,
      resolve_span=resolve_span,
      shard_id=job_id,
      shard_count=job_count,
      task_step_id=task_step_id,
      task_step_description=f'[shard {job_id+1}/{job_count}] map "{map_fn.__name__}"',
    )

  @override
  def to_json(
    self,
    filepath: Union[str, pathlib.Path],
    jsonl: bool = True,
    columns: Optional[Sequence[ColumnId]] = None,
    filters: Optional[Sequence[FilterLike]] = None,
    include_labels: Optional[Sequence[str]] = None,
    exclude_labels: Optional[Sequence[str]] = None,
  ) -> None:
    selection = self._get_selection(columns, filters, include_labels, exclude_labels)
    filepath = os.path.expanduser(filepath)
    self._execute(
      f"COPY ({selection}) TO '{filepath}' " f"(FORMAT JSON, ARRAY {'FALSE' if jsonl else 'TRUE'})"
    )
    log(f'Dataset exported to {filepath}')

  @override
  def to_pandas(
    self,
    columns: Optional[Sequence[ColumnId]] = None,
    filters: Optional[Sequence[FilterLike]] = None,
    include_labels: Optional[Sequence[str]] = None,
    exclude_labels: Optional[Sequence[str]] = None,
  ) -> pd.DataFrame:
    selection = self._get_selection(columns, filters, include_labels, exclude_labels)
    return self._query_df(f'{selection}')

  @override
  def to_csv(
    self,
    filepath: Union[str, pathlib.Path],
    columns: Optional[Sequence[ColumnId]] = None,
    filters: Optional[Sequence[FilterLike]] = None,
    include_labels: Optional[Sequence[str]] = None,
    exclude_labels: Optional[Sequence[str]] = None,
  ) -> None:
    selection = self._get_selection(columns, filters, include_labels, exclude_labels)
    filepath = os.path.expanduser(filepath)
    self._execute(f"COPY ({selection}) TO '{filepath}' (FORMAT CSV, HEADER)")
    log(f'Dataset exported to {filepath}')

  @override
  def to_parquet(
    self,
    filepath: Union[str, pathlib.Path],
    columns: Optional[Sequence[ColumnId]] = None,
    filters: Optional[Sequence[FilterLike]] = None,
    include_labels: Optional[Sequence[str]] = None,
    exclude_labels: Optional[Sequence[str]] = None,
  ) -> None:
    selection = self._get_selection(columns, filters, include_labels, exclude_labels)
    filepath = os.path.expanduser(filepath)
    self._execute(f"COPY ({selection}) TO '{filepath}' (FORMAT PARQUET)")
    log(f'Dataset exported to {filepath}')


def _escape_string_literal(string: str) -> str:
  string = string.replace("'", "''")
  return f"'{string}'"


def _escape_col_name(col_name: str) -> str:
  col_name = col_name.replace('"', '""')
  return f'"{col_name}"'


def _escape_like_value(value: str) -> str:
  value = value.replace('%', '\\%').replace('_', '\\_')
  return f"'%{value}%' ESCAPE '\\'"


def _inner_select(
  sub_paths: list[PathTuple],
  path: PathTuple,
  schema: Schema,
  inner_var: Optional[str] = None,
  empty: bool = False,
  span_from: Optional[tuple[Union[SignalManifest, MapManifest], PathTuple]] = None,
) -> str:
  """Recursively generate the inner select statement for a list of sub paths."""
  current_sub_path = sub_paths[0]
  lambda_var = inner_var + 'x' if inner_var else 'x'
  if not inner_var:
    lambda_var = 'x'
    inner_var = _escape_col_name(current_sub_path[0])
    current_sub_path = current_sub_path[1:]
  # Select the path inside structs. E.g. x['a']['b']['c'] given current_sub_path = [a, b, c].
  path_key = inner_var + ''.join([f'[{_escape_string_literal(p)}]' for p in current_sub_path])
  if len(sub_paths) == 1:
    if span_from:
      manifest, span_path = span_from
      # Older signal manifests (w/o py_version) store spans under `VALUE_KEY` instead of `SPAN_KEY`.
      # TODO(smilkov): Remove this once we bump the semver to breaking.
      span_key = SPAN_KEY if manifest.py_version else VALUE_KEY
      derived_col = _select_sql(span_path, flatten=False, unnest=False, path=path, schema=schema)
      path_key = (
        f'{derived_col}[{path_key}.{span_key}.{TEXT_SPAN_START_FEATURE}+1:'
        f'{path_key}.{span_key}.{TEXT_SPAN_END_FEATURE}]'
      )
    return 'NULL' if empty else path_key
  return (
    f'list_transform({path_key}, {lambda_var} -> '
    f'{_inner_select(sub_paths[1:], path, schema, lambda_var, empty, span_from)})'
  )


def _split_path_into_subpaths_of_lists(leaf_path: PathTuple) -> list[PathTuple]:
  """Split a path into a subpath of lists.

  E.g. [a, b, c, *, d, *, *] gets splits [[a, b, c], [d], [], []].
  """
  sub_paths: list[PathTuple] = []
  offset = 0
  while offset <= len(leaf_path):
    new_offset = (
      leaf_path.index(PATH_WILDCARD, offset)
      if PATH_WILDCARD in leaf_path[offset:]
      else len(leaf_path)
    )
    sub_path = leaf_path[offset:new_offset]
    sub_paths.append(sub_path)
    offset = new_offset + 1
  return sub_paths


def _select_sql(
  sql_path: tuple[str, ...],
  flatten: bool,
  unnest: bool,
  path: PathTuple,
  schema: Schema,
  empty: bool = False,
  span_from: Optional[tuple[Union[SignalManifest, MapManifest], PathTuple]] = None,
) -> str:
  """Create a select column for a path.

  Args:
    sql_path: An internal sql path to the joined wide duckdb table. E.g. ['a', 'b', 'c'].
    flatten: Whether to flatten the result.
    unnest: Whether to unnest the result.
    path: The original path.
    schema: The schema of the dataset.
    empty: Whether to return an empty list (used for embedding signals that don't need the data).
    span_from: The path this span is derived from. If specified, the span will be resolved
      to a substring of the original string.
  """
  sub_paths = _split_path_into_subpaths_of_lists(sql_path)
  selection = _inner_select(sub_paths, path, schema, None, empty, span_from)
  # We only flatten when the result is a deeply nested list to avoid segfault.
  # The nesting list level is a func of subpaths, e.g. subPaths = [[a, b, c], *, *] is 2 levels.
  nesting_level = len(sub_paths) - 1

  # If the parent field is a map, accessing a key returns a list, which increases the nesting level:
  # https://duckdb.org/docs/sql/data_types/map.html
  if len(path) > 1 and schema.has_field(path[:-1]):
    parent_field = schema.get_field(path[:-1])
    if parent_field.dtype and parent_field.dtype.type == 'map':
      nesting_level += 1

  is_result_nested_list = nesting_level >= 2
  if flatten and is_result_nested_list:
    selection = f'flatten({selection})'
  # We only unnest when the result is a list. // E.g. subPaths = [[a, b, c], *].
  is_result_a_list = nesting_level >= 1
  if unnest and is_result_a_list:
    selection = f'unnest({selection})'
  return selection


def read_source_manifest(dataset_path: str) -> SourceManifest:
  """Read the manifest file."""
  # TODO(nsthorat): Overwrite the source manifest with a "source" added if the source is not defined
  # by reading the config yml.
  with open_file(os.path.join(dataset_path, MANIFEST_FILENAME), 'r') as f:
    source_manifest = SourceManifest.model_validate_json(f.read())

  # For backwards compatibility, check if the config has the source and write it back to the
  # source manifest.
  # This can be deleted after some time of migrating people.
  if source_manifest.source == NoSource():
    config_path = os.path.join(dataset_path, OLD_CONFIG_FILENAME)
    if os.path.exists(config_path):
      with open_file(config_path, 'r') as f:
        dataset_config = DatasetConfig(**yaml.safe_load(f))
        if dataset_config.source:
          source_manifest.source = dataset_config.source
      with open_file(os.path.join(dataset_path, MANIFEST_FILENAME), 'w') as f:
        f.write(source_manifest.model_dump_json(indent=2, exclude_none=True))

  return source_manifest


def _signal_dir(enriched_path: PathTuple) -> str:
  """Get the filename prefix for a signal parquet file."""
  path_without_wildcards = (p for p in enriched_path if p != PATH_WILDCARD)
  return os.path.join(*path_without_wildcards)


def _get_parquet_filepath(
  dataset_path: str,
  output_path: PathTuple,
  parquet_filename_prefix: Optional[str] = None,
) -> str:
  # The final parquet file is not sharded.
  parquet_filename = get_parquet_filename(
    parquet_filename_prefix or output_path[-1], shard_index=0, num_shards=1
  )
  path_prefix: Optional[PathTuple]
  if parquet_filename_prefix:
    path_prefix = output_path
  else:
    path_prefix = output_path[:-1] if len(output_path) > 1 else None

  path_prefix = tuple([p for p in output_path if p != PATH_WILDCARD]) if path_prefix else None

  subdir = os.path.join(*path_prefix) if path_prefix else ''

  parquet_rel_filepath = os.path.join(subdir, parquet_filename)
  # Sanitize the filepath name by url-encoding it.
  parquet_rel_filepath = os.path.join(
    *[urllib.parse.quote(p, safe='') for p in parquet_rel_filepath.split(os.sep)]
  )
  return os.path.join(dataset_path, parquet_rel_filepath)


def _jsonl_cache_filepath(
  namespace: str,
  dataset_name: str,
  key: Union[list[str], PathTuple],
  project_dir: Union[str, pathlib.Path],
  is_temporary: bool = False,
  shard_id: Optional[int] = None,
  shard_count: Optional[int] = None,
) -> str:
  """Get the filepath for a map function's cache file."""
  tmp_dir: Optional[tempfile.TemporaryDirectory] = None
  if not is_temporary:
    cache_dir = os.path.join(get_lilac_cache_dir(project_dir), namespace, dataset_name)
  else:
    tmp_dir = tempfile.TemporaryDirectory()
    cache_dir = tmp_dir.name

  filename_prefix = key[-1]

  job_range_suffix = ''
  if shard_id is not None and shard_count:
    job_range_suffix = f'.{shard_id:05d}-of-{shard_count:05d}'

  # The key becomes the subdir.
  key_subdir = key[:-1] if len(key) > 1 else None
  subdir = os.path.join(*key_subdir) if key_subdir else ''
  return os.path.join(
    cache_dir,
    subdir,
    f'{filename_prefix}{job_range_suffix}.jsonl',
  )


def split_column_name(column: str, split_name: str) -> str:
  """Get the name of a split column."""
  return f'{column}.{split_name}'


def split_parquet_prefix(column_name: str, splitter_name: str) -> str:
  """Get the filename prefix for a split parquet file."""
  return f'{column_name}.{splitter_name}'


def _bytes_to_blob_literal(bytes: bytes) -> str:
  """Convert bytes to a blob literal."""
  escaped_hex = re.sub(r'(.{2})', r'\\x\1', bytes.hex())
  return f"'{escaped_hex}'::BLOB"


def _merge_cells(dest_cell: Item, source_cell: Item) -> Item:
  if source_cell is None or isinstance(source_cell, float) and math.isnan(source_cell):
    # Nothing to merge here (missing value).
    return dest_cell
  if isinstance(dest_cell, dict):
    if isinstance(source_cell, list):
      raise ValueError(
        f'Failed to merge cells. Destination is a dict ({dest_cell!r}), '
        f'but source is a list ({source_cell!r}).'
      )
    if isinstance(source_cell, dict):
      res = {**dest_cell}
      for key, value in source_cell.items():
        res[key] = value if key not in dest_cell else _merge_cells(dest_cell[key], value)
      return res
    else:
      return {VALUE_KEY: source_cell, **dest_cell}
  elif isinstance(dest_cell, list):
    if not isinstance(source_cell, list):
      raise ValueError('Failed to merge cells. Destination is a list, but source is not.')
    return [
      _merge_cells(dest_subcell, source_subcell)
      for dest_subcell, source_subcell in zip(dest_cell, source_cell)
    ]
  else:
    # The destination is a primitive.
    if isinstance(source_cell, list):
      raise ValueError(
        f'Failed to merge cells. Destination is a primitive ({dest_cell!r}), '
        f'but source is a list ({source_cell!r}).'
      )
    if isinstance(source_cell, dict):
      return {VALUE_KEY: dest_cell, **source_cell}
    else:
      # Primitives can be merged together if they are equal. This can happen if a user selects a
      # column that is the child of another.
      # NOTE: This can be removed if we fix https://github.com/lilacai/lilac/issues/166.
      if isinstance(dest_cell, float):
        # For floats, explicitly check closeness as precision issues can lead to them not being
        # exactly equal.
        if not math.isclose(source_cell, dest_cell, abs_tol=1e-5):
          raise ValueError(
            f'Cannot merge source "{source_cell!r}" into destination "{dest_cell!r}"'
          )
      else:
        if source_cell != dest_cell:
          raise ValueError(
            f'Cannot merge source "{source_cell!r}" into destination "{dest_cell!r}"'
          )
      return dest_cell


def merge_series(destination: pd.Series, source: pd.Series) -> list[Item]:
  """Merge two series of values recursively."""
  return _merge_cells(destination.tolist(), source.tolist())


def _unique_alias(column: Column) -> str:
  """Get a unique alias for a selection column."""
  if column.signal_udf:
    return make_signal_parquet_id(column.signal_udf, column.path)
  return '.'.join(map(str, column.path))


def _path_contains(parent_path: PathTuple, child_path: PathTuple) -> bool:
  """Check if a path contains another path."""
  if len(parent_path) > len(child_path):
    return False
  return all(parent_path[i] == child_path[i] for i in range(len(parent_path)))


def _path_to_udf_duckdb_path(
  path: PathTuple, path_to_udf_col_name: dict[PathTuple, str]
) -> Optional[PathTuple]:
  first_subpath, *rest_of_path = path
  for parent_path, udf_col_name in path_to_udf_col_name.items():
    # If the user selected udf(document.*.text) as "udf" and wanted to sort by "udf.len", we need to
    # sort by "udf.*.len" where the "*" came from the fact that the udf was applied to a list of
    # "text" fields.
    wildcards = [x for x in parent_path if x == PATH_WILDCARD]
    if _path_contains(parent_path, path):
      return (udf_col_name, *wildcards, *path[len(parent_path) :])
    elif first_subpath == udf_col_name:
      return (udf_col_name, *wildcards, *rest_of_path)

  return None


def _col_destination_path(column: Column, is_computed_signal: bool = False) -> PathTuple:
  """Get the destination path where the output of this selection column will be stored."""
  source_path = column.path

  if not column.signal_udf:
    return source_path

  signal_key = column.signal_udf.key(is_computed_signal=is_computed_signal)
  return (*source_path, signal_key)


def _root_column(manifest: Union[SignalManifest, MapManifest]) -> str:
  """Returns the root column of a signal manifest."""
  field_keys = list(manifest.data_schema.fields.keys())
  if len(field_keys) > 2:
    raise ValueError(
      'Expected at most two fields in signal manifest, '
      f'the rowid and root this signal is enriching. Got {field_keys}.'
    )
  return next(filter(lambda field: field != ROWID, manifest.data_schema.fields.keys()))


def _make_schema_from_path(path: PathTuple, field: Field) -> Schema:
  """Returns a schema that contains only the given path."""
  for sub_path in reversed(path):
    if sub_path == PATH_WILDCARD:
      field = Field(repeated_field=field)
    else:
      field = Field(fields={sub_path: field})
  if not field.fields:
    raise ValueError(f'Invalid path: {path}. Must contain at least one field name.')
  return Schema(fields=field.fields)


def _replace_nan_with_none(df: pd.DataFrame) -> pd.DataFrame:
  """DuckDB returns np.nan for missing field in string column, replace with None for correctness."""
  # TODO(https://github.com/duckdb/duckdb/issues/4066): Remove this once duckdb fixes upstream.
  for col in df.columns:
    if is_object_dtype(df[col]):
      df[col].replace(np.nan, None, inplace=True)
  return df


def _offset_any_span(offset: int, item: Item, schema: Field) -> None:
  """Offsets any spans inplace by the given parent offset."""
  if schema.dtype == STRING_SPAN:
    item = cast(dict, item)
    item[SPAN_KEY][TEXT_SPAN_START_FEATURE] += offset
    item[SPAN_KEY][TEXT_SPAN_END_FEATURE] += offset
  if schema.fields:
    item = cast(dict, item)
    for key, sub_schema in schema.fields.items():
      _offset_any_span(offset, item[key], sub_schema)
  if schema.repeated_field:
    item = cast(list, item)
    for sub_item in item:
      _offset_any_span(offset, sub_item, schema.repeated_field)


def _schema_has_spans(field: Field) -> bool:
  if field.dtype and field.dtype == STRING_SPAN:
    return True
  if field.fields:
    children_have_spans = any(_schema_has_spans(sub_field) for sub_field in field.fields.values())
    if children_have_spans:
      return True
  if field.repeated_field:
    return _schema_has_spans(field.repeated_field)
  return False


def _normalize_bins(bins: Optional[Union[Sequence[Bin], Sequence[float]]]) -> Optional[list[Bin]]:
  if bins is None:
    return None
  if not isinstance(bins[0], (float, int)):
    return cast(list[Bin], bins)
  named_bins: list[Bin] = []
  for i in range(len(bins) + 1):
    start = cast(float, bins[i - 1]) if i > 0 else None
    end = cast(float, bins[i]) if i < len(bins) else None
    named_bins.append((str(i), start, end))
  return named_bins


def _auto_bins(stats: StatsResult, num_bins: int) -> list[Bin]:
  min_val = cast(float, stats.min_val)
  max_val = cast(float, stats.max_val)
  bin_width = (max_val - min_val) / num_bins
  bins: list[Bin] = []
  for i in range(num_bins):
    start = None if i == 0 else min_val + i * bin_width
    end = None if i == num_bins - 1 else min_val + (i + 1) * bin_width
    bins.append((str(i), start, end))
  return bins


def get_labels_sqlite_filename(dataset_output_dir: str, label_name: str) -> str:
  """Get the filepath to the labels file."""
  return os.path.join(dataset_output_dir, f'{label_name}{LABELS_SQLITE_SUFFIX}')
