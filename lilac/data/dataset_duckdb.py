"""The DuckDB implementation of the dataset database."""
import copy
import csv
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
from collections import defaultdict
from contextlib import closing
from datetime import datetime
from importlib import metadata
from typing import Any, Callable, Iterable, Iterator, Literal, Optional, Sequence, Union, cast

import duckdb
import joblib
import numpy as np
import orjson
import pandas as pd
import yaml
from datasets import Dataset as HuggingFaceDataset
from pandas.api.types import is_object_dtype
from pydantic import BaseModel, SerializeAsAny, field_validator
from sklearn.preprocessing import PowerTransformer
from typing_extensions import override

from ..auth import UserInfo
from ..batch_utils import flatten_iter, flatten_path_iter, unflatten_iter
from ..config import (
  OLD_CONFIG_FILENAME,
  DatasetConfig,
  EmbeddingConfig,
  SignalConfig,
  get_dataset_config,
)
from ..dataset_format import DatasetFormatInputSelector, infer_formats
from ..db_manager import remove_dataset_from_cache
from ..embeddings.vector_store import VectorDBIndex
from ..env import env
from ..parquet_writer import ParquetWriter
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
  EMBEDDING_KEY,
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
  EmbeddingInfo,
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
  chunk_embedding,
  column_paths_match,
  is_float,
  is_integer,
  is_ordinal,
  is_temporal,
  merge_schemas,
  normalize_path,
  signal_type_supports_dtype,
)
from ..schema_duckdb import duckdb_schema, escape_col_name, escape_string_literal
from ..signal import (
  Signal,
  TextEmbeddingSignal,
  TopicFn,
  VectorSignal,
  get_signal_by_type,
  resolve_signal,
)
from ..signals.concept_labels import ConceptLabelsSignal
from ..signals.concept_scorer import ConceptSignal
from ..signals.filter_mask import FilterMaskSignal
from ..signals.semantic_similarity import SemanticSimilaritySignal
from ..signals.substring_search import SubstringSignal
from ..source import NoSource, SourceManifest
from ..tasks import (
  TaskExecutionType,
  TaskId,
  get_progress_bar,
)
from ..utils import (
  DebugTimer,
  chunks,
  delete_file,
  get_dataset_output_dir,
  get_lilac_cache_dir,
  log,
  open_file,
)
from . import (
  cluster_titling,
  dataset,  # Imported top-level so they can be mocked.
)
from .clustering import cluster_impl
from .dataset import (
  BINARY_OPS,
  DELETED_LABEL_NAME,
  LIST_OPS,
  MAX_TEXT_LEN_DISTINCT_COUNT,
  MEDIA_AVG_TEXT_LEN,
  RAW_SQL_OPS,
  SAMPLE_AVG_TEXT_LENGTH,
  STRING_OPS,
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
  PivotResult,
  PivotResultOuterGroup,
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
  config_from_dataset,
  get_map_parquet_id,
  make_signal_parquet_id,
)
from .dataset_utils import (
  count_leafs,
  create_json_map_output_schema,
  create_signal_schema,
  flatten_keys,
  get_callable_name,
  get_parquet_filename,
  paths_have_same_cardinality,
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
MAX_AUTO_BINS = 15

BINARY_OP_TO_SQL: dict[BinaryOp, str] = {
  'equals': '=',
  'not_equal': '!=',
  'greater': '>',
  'greater_equal': '>=',
  'less': '<',
  'less_equal': '<=',
}

DUCKDB_CACHE_FILE = 'duckdb_cache.db'


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

  # True when the signal was computed on Lilac Garden.
  use_garden: bool = False

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

  def __init__(self, con: duckdb.DuckDBPyConnection, query: str, output_path: PathTuple):
    self.con = con
    self.query = query
    self.output_path = output_path

  def __iter__(self) -> Iterator[Item]:
    cursor = self.con.cursor()
    pyarrow_reader = cursor.execute(self.query).fetch_record_batch(rows_per_batch=10_000)
    for batch in pyarrow_reader:
      for row in batch.to_pylist():
        yield row['value']

    pyarrow_reader.close()


class DuckDBQueryParams(BaseModel):
  """Representation of a DuckDB select query.

  Most dataset operations involve some combination of DuckDB SQL and Python. The SQL is more
  efficient but the Python is more flexible and enables more complex operations. This class
  encapsulates the set of available options for the initial DuckDB SQL query.

  The columns are not included in this interface for now, because there are too many ways
  that we use selects - all columns, one column, aliasing, unwrapping/flattening, etc.

  Searches and tag inclusions should be compiled down to the equivalent Filter operations.
  Sharding limit/offsets should be handled by computing and setting the desired offsets/limits/sort.
  """

  # Filters encompass anything that goes into a WHERE clause.
  filters: list[Filter] = []
  # A column name to sort by.
  sort_by: Optional[PathTuple] = None
  sort_order: Optional[SortOrder] = SortOrder.ASC
  # If offset is specified, a sort must also be specified for stable results.
  offset: Optional[int] = None
  limit: Optional[int] = None
  include_deleted: bool = False


def _consume_iterator(iterator: Iterator[Any]) -> None:
  """Forces exhaustion of an iterator, without pulling it all into memory."""
  for _ in iterator:
    pass


PivotCacheKey = tuple[PathTuple, PathTuple, GroupsSortBy, SortOrder]


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
    if env('LILAC_USE_TABLE_INDEX', default=False):
      self.con = duckdb.connect(database=os.path.join(self.dataset_path, DUCKDB_CACHE_FILE))
    else:
      self.con = duckdb.connect(database=':memory:')

    # Maps a path and embedding to the vector index. This is lazily generated as needed.
    self._vector_indices: dict[tuple[PathKey, str], VectorDBIndex] = {}
    self.vector_store = vector_store
    self._manifest_lock = threading.Lock()
    self._config_lock = threading.Lock()
    self._vector_index_lock = threading.Lock()
    self._label_file_lock: dict[str, threading.Lock] = defaultdict(threading.Lock)

    # Cache pivot results.
    self._pivot_cache: dict[PivotCacheKey, PivotResult] = {}

    # Create a join table from all the parquet files.
    self.manifest()

    # NOTE: This block is only for backwards compatibility.
    # Make sure the project reflects the dataset.
    project_config = read_project_config(self.project_dir)
    existing_dataset_config = get_dataset_config(project_config, self.namespace, self.dataset_name)
    if not existing_dataset_config:
      dataset_config = config_from_dataset(self)
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
      CREATE OR REPLACE VIEW {escape_col_name(view_name)} AS ({inner_select});
    """
    )

  # NOTE: This is cached, but when the latest mtime of any file in the dataset directory changes
  # the results are invalidated.
  @functools.lru_cache(maxsize=1)
  def _recompute_joint_table(
    self, latest_mtime_micro_sec: int, sqlite_files: tuple[str]
  ) -> DatasetManifest:
    """Recomputes tables and/or views providing a unified view over the dataset.

    High level strategy: create views for each major class of data, then merge all the views.
    CREATE VIEW signals AS (
      ...
    )
    CREATE VIEW labels AS (
      ...
    )
    CREATE VIEW maps AS (
      ...
    )
    CREATE VIEW t AS (
      SELECT sources.*, signals.*, labels.*, maps.*
      FROM sources
      JOIN signals USING (rowid)
      JOIN labels USING (rowid)
      JOIN maps USING (rowid))

    If LILAC_USE_TABLE_INDEX is set, then we apply a further optimization where we create a DuckDB
    table as a cache and index over Sources, Signals, and Maps (excluding labels). We invalidate
    this cache if the underlying data is updated. Labels are excluded from the cache because users
    expect labeling to be a milliseconds-long operations, but recomputing the entire DuckDB table
    can take a second for a 100k row table. Luckily, labels are stored as a indexed sqlite table, so
    we can join them in at query time. The only time this logic is invalid is if an entire label
    type is deleted or created. Therefore the sqlite files are added to the function signature for
    cache busting reasons.

    CREATE TABLE cached_t AS (
      SELECT sources.*, signals.*, maps.*
      FROM sources
      JOIN signals USING (rowid)
      JOIN maps USING (rowid))
    CREATE INDEX ON cached_t (rowid)

    CREATE VIEW t AS (
      SELECT cached_t.*, labels.*
      FROM cached_t
      JOIN labels USING (rowid))
    )

    One final complication is that the duckdb table is now on-disk state that can become invalid
    for a variety of reasons (bugs, lilac version migrations, DuckDB version bumps.)
    The solution is to nuke and recompute the entire cache if anything fails.
    """
    del sqlite_files  # Unused.

    self._pivot_cache.clear()
    self.stats.cache_clear()

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

    # Walk dataset directory and create views for each data type
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
        f'{escape_col_name(manifest.parquet_id)}.{escape_col_name(_root_column(manifest))} '
        f'AS {escape_col_name(manifest.parquet_id)}'
      )
      for manifest in self._signal_manifests
      if manifest.files
    ]
    map_column_selects = [
      (
        f'{escape_col_name(manifest.parquet_id)}.{escape_col_name(_root_column(manifest))} '
        f'AS {escape_col_name(manifest.parquet_id)}'
      )
      for manifest in self._map_manifests
      if manifest.files
    ]
    label_column_selects = []
    for label_name in self._label_schemas.keys():
      col_name = escape_col_name(label_name)
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

    if env('LILAC_USE_TABLE_INDEX', default=False):
      self.con.execute(
        """CREATE TABLE IF NOT EXISTS mtime_cache AS
         (SELECT CAST(0 AS bigint) AS mtime);"""
      )
      db_mtime = self.con.execute('SELECT mtime FROM mtime_cache').fetchone()[0]  # type: ignore
      table_exists = self.con.execute(
        "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = 't'"
      ).fetchone()[0]  # type: ignore
      if db_mtime != latest_mtime_micro_sec or not table_exists:
        table_select_sql = ', '.join(
          [f'{SOURCE_VIEW_NAME}.*'] + signal_column_selects + map_column_selects
        )

        # Get parquet ids for signals, maps
        parquet_ids = [
          manifest.parquet_id
          for manifest in self._signal_manifests + self._map_manifests
          if manifest.files
        ]
        table_join_sql = ' '.join(
          [SOURCE_VIEW_NAME]
          + [
            f'LEFT JOIN {escape_col_name(parquet_id)} USING ({ROWID})' for parquet_id in parquet_ids
          ]
        )
        with DebugTimer(f'Recomputing table+index for {self.dataset_name}...'):
          self.con.execute('UPDATE mtime_cache SET mtime = ?', (latest_mtime_micro_sec,))
          self.con.execute(
            f'CREATE OR REPLACE TABLE cache_t AS (SELECT {table_select_sql} FROM {table_join_sql})'
          )
          self.con.execute(f'CREATE INDEX row_idx ON cache_t ({ROWID})')
          # If not checkpointed, the index will sometimes not be flushed to disk and be recomputed.
          self.con.execute('CHECKPOINT')
      view_select_sql = ', '.join(['cache_t.*'] + label_column_selects)
      view_join_sql = ' '.join(
        ['cache_t']
        + [
          f'LEFT JOIN {escape_col_name(label_name)} USING ({ROWID})'
          for label_name in self._label_schemas.keys()
        ]
      )
      self.con.execute(
        f'CREATE OR REPLACE VIEW t AS (SELECT {view_select_sql} FROM {view_join_sql})'
      )

    else:
      select_sql = ', '.join(
        [f'{SOURCE_VIEW_NAME}.*']
        + signal_column_selects
        + map_column_selects
        + label_column_selects
      )

      # Get parquet ids for signals, maps, and labels.
      parquet_ids = [
        manifest.parquet_id
        for manifest in self._signal_manifests + self._map_manifests
        if manifest.files
      ] + list(self._label_schemas.keys())
      join_sql = ' '.join(
        [SOURCE_VIEW_NAME]
        + [f'LEFT JOIN {escape_col_name(parquet_id)} USING ({ROWID})' for parquet_id in parquet_ids]
      )
      sql_cmd = f"""
        CREATE OR REPLACE VIEW t AS (SELECT {select_sql} FROM {join_sql})
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

    dataset_formats = infer_formats(merged_schema)
    # Choose the first dataset format as the format.
    dataset_format_cls = dataset_formats[0] if dataset_formats else None
    dataset_format = dataset_format_cls() if dataset_format_cls else None

    return DatasetManifest(
      namespace=self.namespace,
      dataset_name=self.dataset_name,
      data_schema=merged_schema,
      num_items=num_items,
      source=self._source_manifest.source,
      dataset_format=dataset_format,
    )

  def _clear_joint_table_cache(self) -> None:
    """Clears the cache for the joint table."""
    self._recompute_joint_table.cache_clear()
    self._pivot_cache.clear()
    self.stats.cache_clear()
    if env('LILAC_USE_TABLE_INDEX', default=False):
      self.con.close()
      pathlib.Path(os.path.join(self.dataset_path, DUCKDB_CACHE_FILE)).unlink(missing_ok=True)
      pathlib.Path(os.path.join(self.dataset_path, DUCKDB_CACHE_FILE + '.wal')).unlink(
        missing_ok=True
      )
      self.con = duckdb.connect(database=os.path.join(self.dataset_path, DUCKDB_CACHE_FILE))

  def _add_map_keys_to_schema(self, path: PathTuple, field: Field, merged_schema: Schema) -> None:
    """Adds the keys of a map to the schema."""
    value_column = 'key'
    duckdb_path = self._leaf_path_to_duckdb_path(path, merged_schema)
    inner_select = self._select_sql(
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
      field.fields[key] = map_dtype.value_field

  @override
  def manifest(self) -> DatasetManifest:
    # Use the latest modification time of all files under the dataset path as the cache key for
    # re-computing the manifest and the joined view.
    with self._manifest_lock:
      all_dataset_files = glob.iglob(os.path.join(self.dataset_path, '**'), recursive=True)
      all_dataset_files = (f for f in all_dataset_files if DUCKDB_CACHE_FILE not in f)
      all_dataset_files = (f for f in all_dataset_files if os.path.isfile(f))
      rapid_change, slow_change = itertools.tee(all_dataset_files)
      rapid_change = (f for f in rapid_change if f.endswith(LABELS_SQLITE_SUFFIX))
      slow_change = (f for f in slow_change if not f.endswith(LABELS_SQLITE_SUFFIX))
      latest_mtime = max(map(os.path.getmtime, slow_change))
      latest_mtime_micro_sec = int(latest_mtime * 1e6)
      try:
        return self._recompute_joint_table(latest_mtime_micro_sec, tuple(sorted(rapid_change)))
      except Exception as e:
        log(e)
        log('Exception encountered while updating joint table cache; recomputing from scratch.')
        self._clear_joint_table_cache()
        return self._recompute_joint_table(latest_mtime_micro_sec, tuple(sorted(rapid_change)))

  @override
  def count(
    self,
    filters: Optional[Sequence[FilterLike]] = None,
    limit: Optional[int] = None,
    include_deleted: bool = False,
  ) -> int:
    manifest = self.manifest()
    filters, _ = self._normalize_filters(filters, col_aliases={}, udf_aliases={}, manifest=manifest)
    query_options = DuckDBQueryParams(filters=filters, limit=limit, include_deleted=include_deleted)
    option_sql = self._compile_select_options(query_options)
    return cast(
      tuple,
      self.con.execute(f'SELECT COUNT(*) FROM (SELECT {ROWID} from t {option_sql})').fetchone(),
    )[0]

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
      # Create the vector db index when it hasn't been created yet.
      if not manifests:
        vector_index = VectorDBIndex(self.vector_store)
        self._vector_indices[index_key] = vector_index
        return vector_index

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

  def _get_cache_len(self, cache_filepath: str, overwrite: bool) -> int:
    """Returns the number of lines in a cache file."""
    if overwrite:
      return 0
    try:
      with open_file(cache_filepath, 'r') as f:
        return len(f.readlines())
    except Exception:
      return 0

  def _select_iterable_values(
    self,
    jsonl_cache_filepath: str,
    select_path: Optional[PathTuple] = None,
    resolve_span: bool = False,
    query_options: Optional[DuckDBQueryParams] = None,
  ) -> Iterator[tuple[str, Item]]:
    """Returns an iterable of (rowid, item), discluding results in the cache filepath."""
    manifest = self.manifest()

    combine_columns = True
    if select_path:
      select_field = manifest.data_schema.get_field(select_path)
      if select_field.fields and select_field.dtype:
        combine_columns = False

    column: Optional[Column] = None
    cols = self._normalize_columns(
      [select_path or (PATH_WILDCARD,)], manifest.data_schema, combine_columns=True
    )
    select_queries: list[str] = []
    columns_to_merge: dict[str, dict[str, Column]] = {}

    final_col_name: Optional[str] = None
    for column in cols:
      path = column.path

      select_sqls: list[str] = []
      final_col_name = column.alias or _unique_alias(column)
      if final_col_name not in columns_to_merge:
        columns_to_merge[final_col_name] = {}

      duckdb_paths = self._column_to_duckdb_paths(
        column, manifest.data_schema, combine_columns=combine_columns
      )
      span_from = self._resolve_span(path, manifest) if resolve_span or column.signal_udf else None

      for parquet_id, duckdb_path in duckdb_paths:
        sql = self._select_sql(
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

        select_sqls.append(f'{sql} AS {escape_string_literal(column_alias)}')
        columns_to_merge[final_col_name][column_alias] = column

      if select_sqls:
        select_queries.append(', '.join(select_sqls))

    options_clause = self._compile_select_options(query_options)

    # Fetch the data from DuckDB.
    con = self.con.cursor()

    select_sql = ', '.join(select_queries)

    # Anti-join removes input rows that are already in the cache so they do not get passed to the
    # map function.
    anti_join = ''
    cache_view = 't_cache_view'

    if os.path.exists(jsonl_cache_filepath):
      with open_file(jsonl_cache_filepath, 'r') as f:
        # Read the first line of the file
        first_line = f.readline()
      if first_line.strip():
        con.execute(
          f"""
          CREATE OR REPLACE VIEW {cache_view} as (
            SELECT {ROWID} FROM read_json_auto(
              '{jsonl_cache_filepath}',
              IGNORE_ERRORS=true,
              hive_partitioning=false,
              format='newline_delimited')
          );
        """
        )
        anti_join = f'ANTI JOIN {cache_view} USING({ROWID})'

    result = con.execute(
      f"""
      SELECT {ROWID}, {select_sql} FROM t
      {anti_join}
      {options_clause}
    """
    )

    while True:
      df_chunk = result.fetch_df_chunk()
      if df_chunk.empty:
        break

      for final_col_name, temp_columns in columns_to_merge.items():
        for temp_col_name, column in temp_columns.items():
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
      if select_path and final_col_name:
        values = df_chunk[final_col_name].tolist()
      else:
        values = df_chunk.to_dict('records')

      yield from zip(row_ids, values)

    con.close()

  def _dispatch_workers(
    self,
    pool_map: joblib.Parallel,
    transform_fn: Callable[[Any], Any],
    output_path: PathTuple,
    jsonl_cache_filepath: str,
    batch_size: Optional[int],
    select_path: Optional[PathTuple] = None,
    overwrite: bool = False,
    query_options: Optional[DuckDBQueryParams] = None,
    resolve_span: bool = False,
    embedding: Optional[str] = None,
    checkpoint_progress: bool = True,
  ) -> Iterator[Item]:
    """Dispatches workers to compute the transform function.

    Requires some complicated massaging of the data.

    Step 1: Get specific columns from specific rows according to input_path, filters/limit. Any
      repeated columns are returned as list[tuple[ROWID, list[value]]]
    Step 2: Flatten the repeated values into a single stream.
    Step 3: Remove None values from that stream.
    Step 4: Optionally batch the stream values.
    Step 5: Feed a stream of optionally batched non-None values to the transform function.
    Step 6: Reverse all of these steps to piece together an iterable of tuple[ROWID, list[value]].
    Step 7: Apply the expected output nesting structure.
    """
    os.makedirs(os.path.dirname(jsonl_cache_filepath), exist_ok=True)
    # Overwrite the file if overwrite is True.
    if overwrite and os.path.exists(jsonl_cache_filepath):
      delete_file(jsonl_cache_filepath)

    # TODO: figure out where the resuming offset should be calculated and passed to
    # the progress bar offset parameter.

    # Step 1
    rows = self._select_iterable_values(
      jsonl_cache_filepath=jsonl_cache_filepath,
      select_path=select_path,
      resolve_span=resolve_span,
      query_options=query_options,
    )

    # Step 4/5
    def batched_pool_map(fn: Callable, items: Iterable[RichData]) -> Iterator[Optional[Item]]:
      map_arg: Iterable[Any]
      if batch_size == -1:
        yield from fn(items)
        return
      elif batch_size is not None:
        map_arg = map(list, chunks(items, batch_size))
      else:
        map_arg = items

      fn = joblib.delayed(fn)
      if batch_size is None:
        yield from pool_map(fn(arg) for arg in map_arg)
      else:
        yield from itertools.chain.from_iterable(pool_map(fn(arg) for arg in map_arg))

    # Tee the results so we can zip the row ids with the outputs.
    inputs_0, inputs_1 = itertools.tee(rows, 2)

    # Tee the values so we can use them for the deep flatten and the deep unflatten.
    input_values = (value for (_, value) in inputs_0)
    output_items: Iterable[Optional[Item]]
    # Flatten the outputs back to the shape of the original data.
    # The output values are flat from the signal. This
    if select_path:
      input_values_0, input_values_1 = itertools.tee(input_values, 2)
      flatten_depth = len([part for part in select_path if part == PATH_WILDCARD])

      if embedding is not None:
        map_fn = transform_fn
        vector_index = self._get_vector_db_index(embedding, select_path)
        inputs_1, inputs_2 = itertools.tee(inputs_1, 2)
        flat_keys = flatten_keys((rowid for (rowid, _) in inputs_2), input_values_0)
        sparse_out = sparse_to_dense_compute(flat_keys, lambda keys: map_fn(vector_index.get(keys)))
      else:
        # Step 2
        flat_input = cast(Iterator[Optional[RichData]], flatten_iter(input_values_0, flatten_depth))
        # Step 3
        sparse_out = sparse_to_dense_compute(
          flat_input,
          lambda x: batched_pool_map(transform_fn, x),  # type: ignore
        )
      # Step 6
      output_items = unflatten_iter(sparse_out, input_values_1, flatten_depth)
    else:
      assert not isinstance(transform_fn, Signal)
      output_items = batched_pool_map(transform_fn, input_values)

    # Step 7
    # Wrap the output items in dicts to match the output path shape.
    nested_spec = _split_path_into_subpaths_of_lists(output_path or ())
    output_items = cast(Iterable[Item], wrap_in_dicts(output_items, nested_spec))

    # Step 6
    output_items = (
      {**item, ROWID: rowid} for (rowid, _), item in zip(inputs_1, output_items) if item
    )

    try:
      if checkpoint_progress:
        with open_file(jsonl_cache_filepath, 'a') as file:
          for item in output_items:
            json.dump(item, file)
            file.write('\n')
            file.flush()
            yield item
      else:
        yield from output_items
    except RuntimeError:
      # NOTE: A RuntimeError exception is thrown when the output_items iterator, which is a zip of
      # input and output items, yields a StopIterator exception.
      raise ValueError(
        'The signal generated a different number of outputs than was given as input. '
        'Please yield `None` for sparse signals. For signals that output multiple values, '
        'please yield an array for each input.'
      )
    except Exception as e:
      raise e

  def _reshard_cache(
    self,
    manifest: DatasetManifest,
    output_path: PathTuple,
    jsonl_cache_filepaths: list[str],
    schema: Optional[Schema] = None,
    is_tmp_output: bool = False,
    parquet_filename_prefix: Optional[str] = None,
    overwrite: bool = False,
  ) -> tuple[str, Schema, Optional[str]]:
    """Reshards the jsonl cache files into a single parquet file.

    When is_tmp_output is true, the results are still merged to a single iterable PyArrow reader.
    """
    # Merge all the shard outputs.
    jsonl_view_name = 'tmp_output'
    con = self.con.cursor()

    if schema:
      schema = schema.model_copy(deep=True)
      if ROWID not in schema.fields:
        schema.fields[ROWID] = Field(dtype=STRING)

    def get_json_query(selection: str) -> str:
      if selection != '*':
        selection += ' AS value'
      return f"""
        SELECT {selection} FROM {'read_json' if schema else 'read_json_auto'}(
          {jsonl_cache_filepaths},
          {f'columns={duckdb_schema(schema)},' if schema else ''}
          hive_partitioning=false,
          ignore_errors=true,
          format='newline_delimited'
        )
      """

    con.execute(f'CREATE OR REPLACE VIEW "{jsonl_view_name}" as ({get_json_query("*")});')

    if not schema:
      reader = con.execute(f'SELECT * from {jsonl_view_name}').fetch_record_batch(
        rows_per_batch=10_000
      )
      schema = arrow_schema_to_schema(reader.schema)
      reader.close()

    parquet_filepath: Optional[str] = None
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
        f"""COPY (SELECT * FROM '{jsonl_view_name}')
          TO {escape_string_literal(parquet_filepath)} (FORMAT PARQUET);"""
      )

      con.close()

    if ROWID in schema.fields:
      del schema.fields[ROWID]

    select_str = self._select_sql(
      output_path, flatten=False, unnest=False, path=output_path, schema=manifest.data_schema
    )
    return get_json_query(select_str), schema, parquet_filepath

  @override
  def get_embeddings(self, embedding: str, rowid: str, path: Union[PathKey, str]) -> list[Item]:
    """Returns the span-level embeddings associated with a specific row value."""
    path = normalize_path(cast(PathTuple, path))
    path = tuple([int(p) if p.isdigit() else p for p in path])

    field_path = tuple([PATH_WILDCARD if isinstance(p, int) else p for p in path])
    vector_index = self._get_vector_db_index(embedding, field_path)

    path_key: PathKey = tuple([rowid, *[p for p in path if isinstance(p, int)]])
    res = list(vector_index.get([path_key]))

    # Convert the internal SpanVector to the public facing chunk_embedding.
    return [
      chunk_embedding(span_vector['span'][0], span_vector['span'][1], span_vector['vector'])
      for span_vector in res[0]
    ]

  @override
  def compute_signal(
    self,
    signal: Signal,
    path: Path,
    filters: Optional[Sequence[FilterLike]] = None,
    limit: Optional[int] = None,
    include_deleted: bool = False,
    overwrite: bool = False,
    task_id: Optional[TaskId] = None,
    use_garden: bool = False,
  ) -> None:
    if isinstance(signal, TextEmbeddingSignal):
      return self.compute_embedding(
        signal.name,
        path,
        filters=filters,
        limit=limit,
        include_deleted=include_deleted,
        overwrite=overwrite,
        task_id=task_id,
        use_garden=use_garden,
      )

    input_path = normalize_path(path)

    manifest = self.manifest()
    filters, _ = self._normalize_filters(filters, col_aliases={}, udf_aliases={}, manifest=manifest)

    signal_col = Column(path=input_path, alias='value', signal_udf=signal)
    output_path = _col_destination_path(signal_col, is_computed_signal=True)

    if not manifest.data_schema.has_field(input_path):
      raise ValueError(f'Cannot compute signal over non-existent path: {input_path}')
    if manifest.data_schema.get_field(input_path).dtype != STRING:
      raise ValueError('Cannot compute signal over a non-string field.')
    if manifest.data_schema.has_field(output_path) and not overwrite:
      raise ValueError('Signal already exists. Use overwrite=True to overwrite.')

    if isinstance(signal, VectorSignal):
      self._assert_embedding_exists(input_path, signal.embedding)

    # Update the project config before computing the signal.
    add_project_signal_config(
      self.namespace,
      self.dataset_name,
      SignalConfig(path=input_path, signal=signal),
      self.project_dir,
    )

    signal.setup_garden() if use_garden else signal.setup()

    jsonl_cache_filepath = _jsonl_cache_filepath(
      namespace=self.namespace,
      dataset_name=self.dataset_name,
      key=output_path,
      project_dir=self.project_dir,
    )

    query_params = DuckDBQueryParams(include_deleted=include_deleted, filters=filters, limit=limit)
    offset = self._get_cache_len(jsonl_cache_filepath, overwrite=overwrite)
    estimated_len = self.count(filters=filters, limit=limit, include_deleted=include_deleted)

    if task_id is not None:
      progress_bar = get_progress_bar(offset=offset, estimated_len=estimated_len, task_id=task_id)
    else:
      progress_bar = get_progress_bar(
        offset=offset,
        estimated_len=estimated_len,
        task_description=f'Compute signal {signal} on {self.dataset_name}:{path}',
      )

    n_jobs = 1 if use_garden else signal.local_parallelism
    prefer = 'threads' if use_garden else signal.local_strategy
    compute_fn = (
      signal.compute_garden
      if use_garden
      else (signal.vector_compute if isinstance(signal, VectorSignal) else signal.compute)
    )
    batch_size = -1 if use_garden else signal.local_batch_size
    _consume_iterator(
      progress_bar(
        self._dispatch_workers(
          joblib.Parallel(n_jobs=n_jobs, prefer=prefer, return_as='generator'),
          compute_fn,
          output_path,
          jsonl_cache_filepath,
          batch_size=batch_size,
          select_path=input_path,
          overwrite=overwrite,
          query_options=query_params,
          embedding=signal.embedding if isinstance(signal, VectorSignal) else None,
        )
      )
    )
    signal.teardown()
    signal_schema = create_signal_schema(signal, input_path, manifest.data_schema)

    _, inferred_schema, parquet_filepath = self._reshard_cache(
      manifest=manifest,
      output_path=output_path,
      schema=signal_schema,
      jsonl_cache_filepaths=[jsonl_cache_filepath],
      parquet_filename_prefix='data',
      overwrite=overwrite,
    )

    if not signal_schema:
      signal_schema = inferred_schema
      signal_schema.get_field(output_path).signal = signal.model_dump(exclude_none=True)

    assert parquet_filepath is not None
    parquet_filename = os.path.basename(parquet_filepath)
    output_dir = os.path.dirname(parquet_filepath)

    signal_manifest_filepath = os.path.join(output_dir, SIGNAL_MANIFEST_FILENAME)

    signal_manifest = SignalManifest(
      files=[parquet_filename],
      data_schema=signal_schema,
      signal=signal,
      enriched_path=input_path,
      parquet_id=make_signal_parquet_id(signal, input_path, is_computed_signal=True),
      py_version=metadata.version('lilac'),
      use_garden=use_garden,
    )
    with open_file(signal_manifest_filepath, 'w') as f:
      f.write(signal_manifest.model_dump_json(exclude_none=True, indent=2))

    log(f'Wrote signal output to {output_dir}')

  @override
  def compute_embedding(
    self,
    embedding: str,
    path: Path,
    filters: Optional[Sequence[FilterLike]] = None,
    limit: Optional[int] = None,
    include_deleted: bool = False,
    overwrite: bool = False,
    task_id: Optional[TaskId] = None,
    use_garden: bool = False,
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

    filters, _ = self._normalize_filters(filters, col_aliases={}, udf_aliases={}, manifest=manifest)

    signal = get_signal_by_type(embedding, TextEmbeddingSignal)(use_garden=use_garden)

    signal.setup_garden() if use_garden else signal.setup()

    signal_col = Column(path=input_path, alias='value', signal_udf=signal)

    output_path = _col_destination_path(signal_col, is_computed_signal=True)
    output_dir = os.path.join(self.dataset_path, _signal_dir(output_path))
    embedding_info = EmbeddingInfo(input_path=input_path, embedding=embedding)
    signal_schema = create_signal_schema(signal, input_path, manifest.data_schema, embedding_info)

    assert signal_schema, 'Signal schema should be defined for `TextEmbeddingSignal`.'

    if manifest.data_schema.has_field(output_path):
      if overwrite:
        self.delete_embedding(embedding, input_path)
      else:
        raise ValueError(
          f'Embedding "{embedding}" already exists at path {input_path}. '
          'Use overwrite=True to overwrite.'
        )

    jsonl_cache_filepath = _jsonl_cache_filepath(
      namespace=self.namespace,
      dataset_name=self.dataset_name,
      key=output_path,
      project_dir=self.project_dir,
    )

    query_params = DuckDBQueryParams(include_deleted=include_deleted, filters=filters, limit=limit)
    offset = self._get_cache_len(jsonl_cache_filepath, overwrite=overwrite)
    estimated_len = self.count(filters=filters, limit=limit, include_deleted=include_deleted)

    if task_id is not None:
      progress_bar = get_progress_bar(offset=offset, estimated_len=estimated_len, task_id=task_id)
    else:
      progress_bar = get_progress_bar(
        offset=offset,
        estimated_len=estimated_len,
        task_description=f'Compute embedding {signal} on {self.dataset_name}:{path}',
      )

    n_jobs = 1 if use_garden else signal.local_parallelism
    prefer = 'threads' if use_garden else signal.local_strategy
    compute_fn = signal.compute_garden if use_garden else signal.compute
    batch_size = -1 if use_garden else signal.local_batch_size

    output_items = progress_bar(
      self._dispatch_workers(
        joblib.Parallel(n_jobs=n_jobs, prefer=prefer, return_as='generator'),
        compute_fn,
        output_path,
        jsonl_cache_filepath,
        batch_size=batch_size,
        select_path=input_path,
        overwrite=overwrite,
        query_options=query_params,
        checkpoint_progress=False,
      )
    )

    vector_index = self._get_vector_db_index(embedding, input_path)
    write_embeddings_to_disk(
      vector_index=vector_index,
      signal_items=output_items,
      output_dir=output_dir,
    )

    signal.teardown()
    gc.collect()

    signal_manifest_filepath = os.path.join(output_dir, SIGNAL_MANIFEST_FILENAME)
    # If the signal manifest already exists, delete it as it will be rewritten after the new signal
    # outputs are run.
    if os.path.exists(signal_manifest_filepath):
      os.remove(signal_manifest_filepath)
      # Recreate all the views, otherwise this could be stale and point to a non existent file.
      self._clear_joint_table_cache()

    signal_manifest = SignalManifest(
      files=[],
      data_schema=signal_schema,
      signal=signal,
      enriched_path=input_path,
      parquet_id=make_signal_parquet_id(signal, input_path, is_computed_signal=True),
      vector_store=self.vector_store,
      py_version=metadata.version('lilac'),
      use_garden=use_garden,
    )

    with open_file(signal_manifest_filepath, 'w') as f:
      f.write(signal_manifest.model_dump_json(exclude_none=True, indent=2))

    log(f'Wrote embedding index to {output_dir}')

  @override
  def delete_embedding(self, embedding: str, path: Path) -> None:
    path = normalize_path(path)
    vector_index = self._get_vector_db_index(embedding, path)
    output_dir = os.path.join(self.dataset_path, _signal_dir((*path, embedding)))
    vector_index.delete(output_dir)

    with self._vector_index_lock:
      # Remove the vector index from the cache so it's recreated.
      del self._vector_indices[(path, embedding)]

    # Delete the signal manifest.
    signal_manifest_filepath = os.path.join(output_dir, SIGNAL_MANIFEST_FILENAME)
    # If the signal manifest already exists, delete it as it will be rewritten after the new signal
    # outputs are run.
    if os.path.exists(signal_manifest_filepath):
      os.remove(signal_manifest_filepath)
      # Recreate all the views, otherwise this could be stale and point to a non existent file.
      self._clear_joint_table_cache()

  @override
  def load_embedding(
    self,
    load_fn: Callable[[Item], Union[np.ndarray, list[Item]]],
    index_path: Path,
    embedding: str,
    overwrite: bool = False,
    task_id: Optional[TaskId] = None,
  ) -> None:
    index_path = normalize_path(index_path)
    # Make sure there are no PATH_WILDCARDS in index_path.
    if any(p == PATH_WILDCARD for p in index_path):
      raise ValueError(
        '`index_path` cannot contain repeated values for `load_embedding`. '
        'If you require this, please file an issue: https://github.com/lilacai/lilac/issues/new'
      )

    manifest = self.manifest()
    index_field = manifest.data_schema.get_field(index_path)
    if index_field.dtype != STRING:
      raise ValueError(f'`index_path` "{index_path}" must be a string field.')

    # We create an implicit embedding signal for user-loaded embeddings.
    try:
      signal_cls = get_signal_by_type(embedding, TextEmbeddingSignal)
    except Exception:
      raise ValueError(
        f'Embedding "{embedding}" not found. You must register an embedding with '
        '`ll.register_embedding()` before loading embeddings. For more details, see: '
        'https://docs.lilacml.com/datasets/dataset_embeddings.html'
      )
    signal = signal_cls()
    signal.setup()

    signal_col = Column(path=index_path, alias='value', signal_udf=signal)

    output_path = _col_destination_path(signal_col, is_computed_signal=True)
    output_dir = os.path.join(self.dataset_path, _signal_dir(output_path))
    signal_schema = create_signal_schema(signal, index_path, manifest.data_schema)

    assert signal_schema, 'Signal schema should be defined for `TextEmbeddingSignal`.'
    if manifest.data_schema.has_field(output_path):
      if overwrite:
        self.delete_embedding(embedding, index_path)
      else:
        raise ValueError(
          f'Embedding "{embedding}" already exists at path {index_path}. '
          'Use overwrite=True to overwrite.'
        )

    estimated_len = self.count()

    if task_id is not None:
      progress_bar = get_progress_bar(estimated_len=estimated_len, task_id=task_id)
    else:
      progress_bar = get_progress_bar(
        estimated_len=estimated_len,
        task_description=f'Load embedding {embedding} on {self.dataset_name}:{index_path}',
      )

    jsonl_cache_filepath = _jsonl_cache_filepath(
      namespace=self.namespace,
      dataset_name=self.dataset_name,
      key=output_path,
      project_dir=self.project_dir,
    )

    def _validated_load_fn(item: Item) -> Union[np.ndarray, list[Item]]:
      res = load_fn(item)

      if isinstance(res, np.ndarray):
        texts = list(flatten_path_iter(item, path=index_path))
        # We currently only support non-repeated texts.
        text = texts[0]
        return [chunk_embedding(0, len(text), res)]
      elif isinstance(res, list):
        for chunk in res:
          assert EMBEDDING_KEY in chunk and SPAN_KEY in chunk, (
            f'load_fn must return a list of `ll.chunk_embedding()` or a single numpy array. '
            f'Got: {type(res)}'
          )
        return res
      else:
        raise ValueError(
          f'load_fn must return a list of `ll.chunk_embedding()` or a numpy array. Got: {type(res)}'
        )

    output_items = progress_bar(
      self._dispatch_workers(
        joblib.Parallel(n_jobs=1, prefer='threads', return_as='generator'),
        _validated_load_fn,
        output_path,
        jsonl_cache_filepath,
        batch_size=None,
        select_path=None,  # Select the entire row.
        overwrite=overwrite,
        query_options=None,
        checkpoint_progress=False,
      )
    )

    vector_index = self._get_vector_db_index(embedding, index_path)
    write_embeddings_to_disk(
      vector_index=vector_index,
      signal_items=output_items,
      output_dir=output_dir,
    )
    gc.collect()

    signal_manifest_filepath = os.path.join(output_dir, SIGNAL_MANIFEST_FILENAME)
    # If the signal manifest already exists, delete it as it will be rewritten after the new signal
    # outputs are run.
    if os.path.exists(signal_manifest_filepath):
      os.remove(signal_manifest_filepath)
      # Recreate all the views, otherwise this could be stale and point to a non existent file.
      self._clear_joint_table_cache()

    signal_manifest = SignalManifest(
      files=[],
      data_schema=signal_schema,
      signal=signal,
      enriched_path=index_path,
      parquet_id=make_signal_parquet_id(signal, index_path, is_computed_signal=True),
      vector_store=self.vector_store,
      py_version=metadata.version('lilac'),
      use_garden=False,
    )

    with open_file(signal_manifest_filepath, 'w') as f:
      f.write(signal_manifest.model_dump_json(exclude_none=True, indent=2))

    log(f'Wrote embedding index to {output_dir}')

  @override
  def delete_column(self, path: Path) -> None:
    path = normalize_path(path)

    # Sanity checks.
    manifest = self.manifest()
    if not manifest.data_schema.has_field(path):
      raise ValueError(f'Cannot delete path: {path}. It does not exist')
    field = manifest.data_schema.get_field(path)

    if field.signal:
      return self.delete_signal(path)

    if not field.map:
      raise ValueError(f'Cannot delete path: {path} since it was not created by dataset.map()')

    jsonl_cache_filepath = _jsonl_cache_filepath(
      namespace=self.namespace,
      dataset_name=self.dataset_name,
      key=path,
      project_dir=self.project_dir,
    )
    if os.path.exists(jsonl_cache_filepath):
      delete_file(jsonl_cache_filepath)

    parquet_filepath = _get_parquet_filepath(dataset_path=self.dataset_path, output_path=path)
    delete_file(parquet_filepath)

    parquet_dir = os.path.dirname(parquet_filepath)
    prefix = '.'.join(path)
    map_manifest_filepath = os.path.join(parquet_dir, f'{prefix}.{MAP_MANIFEST_SUFFIX}')
    delete_file(map_manifest_filepath)
    self._clear_joint_table_cache()

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
    self._clear_joint_table_cache()

  def _validate_filters(
    self, filters: Sequence[Filter], col_aliases: dict[str, PathTuple], manifest: DatasetManifest
  ) -> None:
    for filter in filters:
      if filter.path[0] in col_aliases:
        # This is a filter on a column alias, which is always allowed.
        continue

      if filter.op in RAW_SQL_OPS:
        # Assume that raw SQL is correct.
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
      if filter.op in STRING_OPS:
        if current_field.dtype != STRING:
          raise ValueError(
            f'Unable to apply string filter to path {filter.path} of type {current_field.dtype}. '
          )
        if filter.op in ('length_shorter', 'length_shorter'):
          try:
            filter.value = int(filter.value)  # type: ignore
          except ValueError:
            raise ValueError(f'TypeError: String length {filter.value!r} should be an integer. ')

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
  def stats(self, leaf_path: Path, include_deleted: bool = False) -> StatsResult:
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
    inner_select = self._select_sql(
      duckdb_path,
      flatten=True,
      unnest=True,
      path=path,
      schema=manifest.data_schema,
      span_from=self._resolve_span(path, manifest),
    )

    if manifest.data_schema.has_field((DELETED_LABEL_NAME,)) and not include_deleted:
      where_clause = f'WHERE {DELETED_LABEL_NAME} IS NULL'
    else:
      where_clause = ''

    # Compute the average length of text fields.
    avg_text_length: Optional[int] = None
    if leaf.dtype in (STRING, STRING_SPAN):
      avg_length_query = f"""
        SELECT avg(length(val))
        FROM (SELECT {inner_select} AS val FROM t {where_clause})
        USING SAMPLE {SAMPLE_AVG_TEXT_LENGTH};
      """
      row = self._query(avg_length_query)[0]
      if row[0] is not None:
        avg_text_length = int(row[0])

    total_count_query = (
      f'SELECT count(val) FROM (SELECT {inner_select} as val FROM t {where_clause})'
    )
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
        FROM (SELECT {inner_select} AS val FROM t {where_clause}) USING SAMPLE {sample_size};
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
        SELECT MIN(val) AS minVal, MAX(val) AS maxVal,
        FROM (SELECT {inner_select} as val FROM t {where_clause})
        {'WHERE NOT isnan(val)' if is_float(leaf.dtype) else ''}
      """
      row = self._query(min_max_query)[0]
      result.min_val, result.max_val = row
      sample_query = f"""
        SELECT COALESCE(ARRAY_AGG(val), [])
        FROM (SELECT {inner_select} as val FROM t {where_clause})
        WHERE val != 0 {'AND NOT isnan(val)' if is_float(leaf.dtype) else ''}
        USING SAMPLE 100;
      """
      result.value_samples = list(self._query(sample_query)[0][0])

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
    include_deleted: bool = False,
    searches: Optional[Sequence[Search]] = None,
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
    stats = self.stats(leaf_path, include_deleted=include_deleted)

    leaf_is_float = is_float(leaf.dtype)
    leaf_is_integer = is_integer(leaf.dtype)
    if not leaf.categorical and (leaf_is_float or leaf_is_integer):
      if named_bins is None:
        # Auto-bin.
        named_bins = _auto_bins(stats)

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
    inner_select = self._select_sql(
      duckdb_path,
      flatten=True,
      unnest=True,
      path=path,
      schema=manifest.data_schema,
      span_from=self._resolve_span(path, manifest),
    )

    filters, _ = self._normalize_filters(filters, col_aliases={}, udf_aliases={}, manifest=manifest)
    if not include_deleted and manifest.data_schema.has_field((DELETED_LABEL_NAME,)):
      filters.append(Filter(path=(DELETED_LABEL_NAME,), op='not_exists'))

    filters = self._add_searches_to_filters(searches or [], filters)

    filter_queries = self._create_where(manifest, filters)

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

  @override
  def pivot(
    self,
    outer_path: Path,
    inner_path: Path,
    searches: Optional[Sequence[Search]] = None,
    filters: Optional[Sequence[FilterLike]] = None,
    sort_by: Optional[GroupsSortBy] = GroupsSortBy.COUNT,
    sort_order: Optional[SortOrder] = SortOrder.DESC,
  ) -> PivotResult:
    if not inner_path or not outer_path:
      raise ValueError('both `outer_path` and `inner_path` must be provided')
    sort_by = sort_by or GroupsSortBy.COUNT
    sort_order = sort_order or SortOrder.DESC
    inner_path = normalize_path(inner_path)
    outer_path = normalize_path(outer_path)

    pivot_key = (outer_path, inner_path, sort_by, sort_order)
    use_cache = not filters and not searches
    if use_cache and pivot_key in self._pivot_cache:
      return self._pivot_cache[pivot_key]

    manifest = self.manifest()
    inner_leaf = manifest.data_schema.get_field(inner_path)
    outer_leaf = manifest.data_schema.get_field(outer_path)

    # Find the inner-most inner leaf in case this field is repeated.
    while inner_leaf.repeated_field:
      inner_leaf = inner_leaf.repeated_field
      inner_path = (*inner_path, PATH_WILDCARD)

    # Find the inner-most outer leaf in case this field is repeated.
    while outer_leaf.repeated_field:
      outer_leaf = outer_leaf.repeated_field
      outer_path = (*outer_path, PATH_WILDCARD)

    if not inner_leaf.dtype:
      raise ValueError(f'Inner path "{inner_path}" is not a leaf in the dataset')
    if not outer_leaf.dtype:
      raise ValueError(f'Outer path "{outer_path}" is not a leaf in the dataset')

    if inner_leaf.dtype.type == 'map':
      raise ValueError(f'Cannot compute pivot on a map field "{inner_path}".')
    if is_ordinal(inner_leaf.dtype):
      raise ValueError(f'Cannot compute pivot on an ordinal field "{inner_path}".')
    if outer_leaf.dtype.type == 'map':
      raise ValueError(f'Cannot compute pivot on an map field "{outer_path}".')
    if is_ordinal(outer_leaf.dtype):
      raise ValueError(f'Cannot compute pivot on an ordinal field "{outer_path}".')

    if self.stats(inner_path).approx_count_distinct >= dataset.TOO_MANY_DISTINCT:
      return PivotResult(too_many_distinct=True, outer_groups=[])
    if self.stats(outer_path).approx_count_distinct >= dataset.TOO_MANY_DISTINCT:
      return PivotResult(too_many_distinct=True, outer_groups=[])

    count_column = GroupsSortBy.COUNT.value
    value_column = GroupsSortBy.VALUE.value
    inner_column = 'inner'

    inner_duckdb_path = self._leaf_path_to_duckdb_path(inner_path, manifest.data_schema)
    inner_select = self._select_sql(
      inner_duckdb_path,
      flatten=True,
      unnest=True,
      path=inner_path,
      schema=manifest.data_schema,
      span_from=self._resolve_span(inner_path, manifest),
    )

    outer_duckdb_path = self._leaf_path_to_duckdb_path(outer_path, manifest.data_schema)
    outer_select = self._select_sql(
      outer_duckdb_path,
      flatten=True,
      unnest=True,
      path=outer_path,
      schema=manifest.data_schema,
      span_from=self._resolve_span(outer_path, manifest),
    )
    filters, _ = self._normalize_filters(filters, col_aliases={}, udf_aliases={}, manifest=manifest)

    # Add search where queries.
    filters = self._add_searches_to_filters(searches or [], filters)

    where_query = self._compile_select_options(
      DuckDBQueryParams(filters=filters, include_deleted=False)
    )

    query = f"""
      WITH tuples AS (
        SELECT {outer_select} AS out_val, {inner_select} AS in_val
        FROM t
        {where_query}
      ),
      tuple_counts AS (
        SELECT out_val, in_val, count() AS c FROM tuples
        GROUP BY out_val, in_val
      )
      SELECT
        out_val AS {value_column},
        SUM(c) AS {count_column},
        list({{'{value_column}': in_val, '{count_column}': c}} ORDER BY c DESC) AS {inner_column}
      FROM tuple_counts
      GROUP BY out_val
      ORDER BY {sort_by.value} {sort_order.value}, {value_column}
    """
    df = self._query_df(query)
    outer_groups: list[PivotResultOuterGroup] = []
    for out_val, count, inner_structs in df.itertuples(index=False, name=None):
      inner: list[tuple[Optional[str], int]] = [
        (struct[value_column], struct[count_column]) for struct in inner_structs
      ]
      outer_groups.append(PivotResultOuterGroup(value=out_val, count=count, inner=inner))
    result = PivotResult(outer_groups=outer_groups)
    if use_cache:
      self._pivot_cache[pivot_key] = result
    return result

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
    resolve_span: bool = False,
    combine_columns: bool = False,
    include_deleted: bool = False,
    exclude_signals: bool = False,
    user: Optional[UserInfo] = None,
  ) -> SelectRowsResult:
    manifest = self.manifest()
    cols = self._normalize_columns(columns, manifest.data_schema, combine_columns)
    offset = offset or 0
    schema = manifest.data_schema

    searches = searches or []
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

    # Remove fields that are produced by signals.
    if exclude_signals:
      signal_paths: list[PathTuple] = []
      for signal_manifest in self._signal_manifests:
        signal_paths.extend(list(signal_manifest.data_schema.leafs.keys()))

      cols = [col for col in cols if col.path not in signal_paths]

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
    # Choose the first sort order as we only support a single sort order for now. If the user didn't
    # provide any sort_by, we default to UUID, ascending.
    sort_order = sort_results[0].order if sort_results else SortOrder.ASC

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
    filters = self._add_searches_to_filters(searches, filters)

    if not include_deleted and manifest.data_schema.has_field((DELETED_LABEL_NAME,)):
      filters.append(Filter(path=(DELETED_LABEL_NAME,), op='not_exists'))

    filter_queries = self._create_where(manifest, filters)
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

    row_id_selected = False
    for column in cols:
      if column.path == (ROWID,):
        row_id_selected = True
      path = column.path
      # If the signal is vector-based, we don't need to select the actual data, just the rowids
      # plus an arbitrarily nested array of `None`s`.
      empty = bool(column.signal_udf and schema.get_field(path).dtype == EMBEDDING)

      select_sqls: list[str] = []
      final_col_name = column.alias or _unique_alias(column)
      if final_col_name not in columns_to_merge:
        columns_to_merge[final_col_name] = {}

      duckdb_paths = self._column_to_duckdb_paths(column, schema, combine_columns, exclude_signals)
      span_from = self._resolve_span(path, manifest) if resolve_span or column.signal_udf else None

      for parquet_id, duckdb_path in duckdb_paths:
        sql = self._select_sql(
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
        select_sqls.append(f'{sql} AS {escape_string_literal(temp_column_name)}')
        columns_to_merge[final_col_name][temp_column_name] = column

        udf_schema = column.signal_udf and column.signal_udf.fields()
        if span_from and udf_schema and _schema_has_spans(udf_schema):
          sql = self._select_sql(
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
          select_sqls.append(f'{sql} AS {escape_string_literal(temp_offset_column_name)}')
          temp_column_to_offset_column[temp_column_name] = (temp_offset_column_name, udf_schema)

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

      sort_sql = self._select_sql(sql_path, flatten=True, unnest=False, path=path, schema=schema)
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

    # Always append the rowid to the sort order to ensure stable results.
    sort_sql_before_udf.append(ROWID)
    if sort_sql_after_udf and row_id_selected:
      sort_sql_after_udf.append(ROWID)

    order_query = ''
    if sort_sql_before_udf:
      # TODO(smilkov): Make the sort order also a list to align with the sort_by list.
      sort_with_order = [f'{sql} {sort_order.value}' for sql in sort_sql_before_udf]
      order_query = f'ORDER BY {", ".join(sort_with_order)}'

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

        if isinstance(signal, VectorSignal):
          embedding_signal = signal
          self._assert_embedding_exists(udf_col.path, embedding_signal.embedding)

          vector_store = self._get_vector_db_index(embedding_signal.embedding, udf_col.path)
          flat_keys = flatten_keys(df[ROWID], input)
          signal_out = sparse_to_dense_compute(
            flat_keys, lambda keys: embedding_signal.vector_compute(vector_store.get(keys))
          )
          df[signal_column] = list(unflatten_iter(signal_out, input))
        else:
          num_rich_data = count_leafs(input)
          flat_input = cast(Iterator[Optional[RichData]], flatten_iter(input))
          signal_out = sparse_to_dense_compute(
            flat_input, lambda x: signal.compute(cast(Iterable[RichData], x))
          )
          signal_out_list = list(signal_out)
          if signal_column in temp_column_to_offset_column:
            offset_column_name, field = temp_column_to_offset_column[signal_column]
            nested_spans: Iterable[Item] = df[offset_column_name]
            flat_spans = flatten_iter(nested_spans)
            for text_span, item in zip(flat_spans, signal_out_list):
              _offset_any_span(cast(int, text_span[SPAN_KEY][TEXT_SPAN_START_FEATURE]), item, field)

          if len(signal_out_list) != num_rich_data:
            raise ValueError(
              f'The signal generated {len(signal_out_list)} values but the input data had '
              f"{num_rich_data} values. This means the signal either didn't generate a "
              '"None" for a sparse output, or generated too many items.'
            )

          df[signal_column] = list(unflatten_iter(signal_out_list, input))

        signal.teardown()

    if not df.empty and (udf_filters or sort_sql_after_udf):
      # Re-upload the udf outputs to duckdb so we can filter/sort on them.
      rel = con.from_df(df)

      if udf_filters:
        udf_filter_queries = self._create_where(manifest, udf_filters)
        if udf_filter_queries:
          rel = rel.filter(' AND '.join(udf_filter_queries))
          count = rel.count('*').fetchone()
          assert count is not None
          (total_num_rows,) = count

      if sort_sql_after_udf:
        rel = rel.order(', '.join([f'{s} {sort_order.value}' for s in sort_sql_after_udf]))

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
    exclude_signals: bool = False,
  ) -> SelectRowsSchemaResult:
    """Returns the schema of the result of `select_rows` above with the same arguments."""
    if not combine_columns:
      raise NotImplementedError(
        'select_rows_schema with combine_columns=False is not yet supported.'
      )
    manifest = self.manifest()
    cols = self._normalize_columns(columns, manifest.data_schema, combine_columns)

    searches = searches or []
    search_udfs = self._search_udfs(searches, manifest)
    cols.extend([search_udf.udf for search_udf in search_udfs])

    # Remove fields that are produced by signals.
    if exclude_signals:
      signal_paths: list[PathTuple] = []
      for signal_manifest in self._signal_manifests:
        signal_paths.extend(list(signal_manifest.data_schema.leafs.keys()))

      cols = [col for col in cols if col.path not in signal_paths]

    udfs: list[SelectRowsSchemaUDF] = []
    col_schemas: list[Schema] = []
    for col in cols:
      dest_path = _col_destination_path(col)
      if col.signal_udf and not exclude_signals:
        udfs.append(SelectRowsSchemaUDF(path=dest_path, alias=col.alias))
        field = col.signal_udf.fields()
        assert field, f'Signal {col.signal_udf.name} needs `Signal.fields` defined when run as UDF.'
        field.signal = col.signal_udf.model_dump(exclude_none=True)
      elif manifest.data_schema.has_field(dest_path):
        field = manifest.data_schema.get_field(dest_path)
      else:
        # This column might refer to an output of a udf. We postpone validation to later.
        continue

      # Delete any signals from the schema if we are excluding signals.
      if exclude_signals:
        field = copy.deepcopy(field)
        field = _remove_signals_from_field(field)
        assert field is not None

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
    sort_by: Optional[Sequence[Path]] = None,
    sort_order: Optional[SortOrder] = SortOrder.DESC,
    limit: Optional[int] = None,
    offset: Optional[int] = 0,
    include_deleted: bool = False,
    value: Optional[str] = 'true',
  ) -> int:
    created = datetime.now()
    # If filters and searches are defined with row_ids, add this as a filter.
    if row_ids:
      filters = list(filters) if filters else []
      filters.append(Filter(path=(ROWID,), op='in', value=list(row_ids)))

    insert_row_ids = (
      row[ROWID]
      for row in self.select_rows(
        columns=[ROWID],
        searches=searches,
        filters=filters,
        sort_by=sort_by,
        sort_order=sort_order,
        limit=limit,
        offset=offset,
        include_deleted=include_deleted,
      )
    )

    labels_filepath = get_labels_sqlite_filename(self.dataset_path, name)

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

    # Any deleted rows will cause statistics to be out of date.
    if num_labels > 0 and name == DELETED_LABEL_NAME:
      self.stats.cache_clear()
      self._pivot_cache.clear()

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
    sort_by: Optional[Sequence[Path]] = None,
    sort_order: Optional[SortOrder] = SortOrder.DESC,
    limit: Optional[int] = None,
    offset: Optional[int] = 0,
    include_deleted: bool = False,
  ) -> int:
    # Check if the label file exists.
    labels_filepath = get_labels_sqlite_filename(self.dataset_path, name)

    if not os.path.exists(labels_filepath):
      raise ValueError(f'Label with name "{name}" does not exist.')

    # If filters and searches are defined with row_ids, add this as a filter.
    if row_ids:
      filters = list(filters) if filters else []
      filters.append(Filter(path=(ROWID,), op='in', value=list(row_ids)))

    remove_row_ids = [
      row[ROWID]
      for row in self.select_rows(
        columns=[ROWID],
        searches=searches,
        filters=filters,
        sort_by=sort_by,
        sort_order=sort_order,
        limit=limit,
        offset=offset,
        include_deleted=include_deleted,
      )
    ]

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
        if name != DELETED_LABEL_NAME:
          count = conn.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0]
          if count == 0:
            delete_file(labels_filepath)

    if remove_row_ids and name == DELETED_LABEL_NAME:
      self.stats.cache_clear()
      self._pivot_cache.clear()

    return len(remove_row_ids)

  @override
  def media(self, item_id: str, leaf_path: Path) -> MediaResult:
    raise NotImplementedError('Media is not yet supported for the DuckDB implementation.')

  def _resolve_span(self, span_path: PathTuple, manifest: DatasetManifest) -> Optional[PathTuple]:
    schema = manifest.data_schema
    if not schema.has_field(span_path):
      return None
    span_field = schema.get_field(span_path)
    if not span_field.dtype == STRING_SPAN:
      return None

    if span_field.map and span_field.map.input_path:
      return span_field.map.input_path

    # Find the original text, which is the closest parent of `path` above the signal root.
    for i in reversed(range(len(span_path))):
      sub_path = span_path[:i]
      sub_field = schema.get_field(sub_path)
      if sub_field.map and sub_field.map.input_path:
        return sub_field.map.input_path
      if sub_field.dtype == STRING:
        return sub_path

    raise ValueError('Cannot find the source path for the enriched path: {path}')

  def _leaf_path_to_duckdb_path(self, leaf_path: PathTuple, schema: Schema) -> PathTuple:
    [(_, duckdb_path), *rest] = self._column_to_duckdb_paths(
      Column(leaf_path), schema, combine_columns=False
    )
    return duckdb_path

  def _column_to_duckdb_paths(
    self, column: Column, schema: Schema, combine_columns: bool, exclude_signals: bool = False
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
      if exclude_signals and isinstance(m, SignalManifest):
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
          path, op, value = filter
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
    filters: Sequence[Filter],
  ) -> list[str]:
    if not filters:
      return []
    sql_filter_queries: list[str] = []

    # Add filter where queries.
    for f in filters:
      if f.op in RAW_SQL_OPS:
        sql_filter_queries.append(f.path[0])
        continue
      duckdb_path = self._leaf_path_to_duckdb_path(f.path, manifest.data_schema)
      select_str = self._select_sql(
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
          filter_val = escape_string_literal(filter_val)
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
      elif f.op in STRING_OPS:
        if f.op == 'length_shorter':
          filter_val = cast(int, f.value)
          filter_query = f'length({select_str}) <= {filter_val}'
        elif f.op == 'length_longer':
          filter_val = cast(int, f.value)
          filter_query = f'length({select_str}) >= {filter_val}'
        elif f.op == 'ilike':
          filter_val = cast(str, f.value)
          filter_query = f'{select_str} ILIKE {_escape_like_value(filter_val)}'
        elif f.op == 'regex_matches':
          filter_val = cast(str, f.value)
          filter_query = f'regexp_matches({select_str}, {escape_string_literal(filter_val)})'
        elif f.op == 'not_regex_matches':
          filter_val = cast(str, f.value)
          filter_query = f'NOT regexp_matches({select_str}, {escape_string_literal(filter_val)})'
        else:
          raise ValueError(f'String op: {f.op} is not yet supported')
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
          filter_list_val = [escape_string_literal(val) for val in filter_list_val]
          if len(filter_list_val) == 1:
            filter_query = f'{select_str} = {filter_list_val[0]}'
          else:
            filter_val = f'({", ".join(filter_list_val)})'
            filter_query = f'{select_str} IN {filter_val}'

            # Optimization for "rowid IN (...)" queries - there is an index on rowid, but
            # duckdb does a full index scan when the IN clause is present, instead of the hash join.
            # So, we insert a range clause to limit the extent of the index scan. This optimization
            # works well because nearly all of our queries are sorted by rowid, meaning that min/max
            # will narrow down the index scan to a small range.
            if env('LILAC_USE_TABLE_INDEX', default=False) and ROWID in select_str:
              min_row, max_row = min(filter_list_val), max(filter_list_val)
              filter_query += f' AND {ROWID} BETWEEN {min_row} AND {max_row}'
              # wrap in parens to isolate from other filters, just in case?
              filter_query = f'({filter_query})'
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
      [f'{escape_col_name(path_comp)}' if quote_each_part else str(path_comp) for path_comp in path]
    )

  def _compile_include_exclude_filters(
    self,
    include_labels: Optional[Sequence[str]] = None,
    exclude_labels: Optional[Sequence[str]] = None,
  ) -> Sequence[Filter]:
    exclude_labels = exclude_labels or []
    manifest = self.manifest()

    filters = []

    if include_labels:
      include_filters = [Filter(path=(label,), op='exists') for label in include_labels]
      include_labels_query = f"({' OR '.join(self._create_where(manifest, include_filters))})"
      filters.append(Filter(path=(include_labels_query,), op='raw_sql'))

    for label in exclude_labels:
      filters.append(Filter(path=(label,), op='not_exists'))
    return filters

  def _compile_select_options(self, query_options: Optional[DuckDBQueryParams]) -> str:
    """Compiles SQL WHERE/ORDER BY/LIMIT clauses for select queries."""
    if query_options is None:
      return ''
    manifest = self.manifest()
    where_clause = ''
    filters = query_options.filters
    if not query_options.include_deleted and manifest.data_schema.has_field((DELETED_LABEL_NAME,)):
      filters.append(Filter(path=(DELETED_LABEL_NAME,), op='not_exists'))
    filter_queries = self._create_where(manifest, query_options.filters)
    if filter_queries:
      where_clause = f"WHERE {' AND '.join(filter_queries)}"

    limit_clause = ''
    if query_options.limit:
      limit_clause = f'LIMIT {query_options.limit}'
      if query_options.offset:
        limit_clause += f' OFFSET {query_options.offset}'

    sort_path = query_options.sort_by
    sort_order = query_options.sort_order or SortOrder.ASC
    order_clause = ''
    if sort_path:
      self._validate_sort_path(sort_path, manifest.data_schema)
      sql_path = self._leaf_path_to_duckdb_path(sort_path, manifest.data_schema)
      sort_sql = self._select_sql(
        sql_path, flatten=True, unnest=False, path=sort_path, schema=manifest.data_schema
      )
      has_repeated_field = any(subpath == PATH_WILDCARD for subpath in sql_path)
      if has_repeated_field:
        sort_sql = (
          f'list_min({sort_sql})' if sort_order == SortOrder.ASC else f'list_max({sort_sql})'
        )

      order_clause = f'ORDER BY {sort_sql} {sort_order.value}'

    return f'{where_clause} {order_clause} {limit_clause}'

  @override
  def map(
    self,
    map_fn: MapFn,
    input_path: Optional[Path] = None,
    output_path: Optional[Path] = None,
    overwrite: bool = False,
    resolve_span: bool = False,
    batch_size: Optional[int] = None,
    filters: Optional[Sequence[FilterLike]] = None,
    limit: Optional[int] = None,
    sort_by: Optional[Path] = None,
    sort_order: Optional[SortOrder] = SortOrder.ASC,
    include_deleted: bool = False,
    num_jobs: int = 1,
    execution_type: TaskExecutionType = 'threads',
    embedding: Optional[str] = None,
    schema: Optional[Field] = None,
    task_id: Optional[TaskId] = None,
  ) -> Iterable[Item]:
    is_tmp_output = output_path is None
    manifest = self.manifest()

    input_path = normalize_path(input_path) if input_path else None
    if input_path and not manifest.data_schema.has_field(input_path):
      raise ValueError(f'Input path {input_path} does not exist in the dataset.')

    # Validate output_path.
    if output_path is not None:
      output_path = normalize_path(output_path)
      output_parent = output_path[:-1]
      if output_parent:
        if not manifest.data_schema.has_field(output_parent):
          raise ValueError(f'Invalid output path. The parent {output_parent} does not exist.')

        assert paths_have_same_cardinality(
          input_path or tuple(), output_parent
        ), (
          f'`input_path` {input_path} and `output_path` {output_path} have different cardinalities.'
        )

    map_fn_name = get_callable_name(map_fn)
    # If the user didn't provide an output_path, we make a temporary one so that we can store the
    # output JSON objects in the cache, represented in the right hierarchy.
    if output_path is None:
      output_path = (map_fn_name,)

    parquet_filepath: Optional[str] = None
    if not is_tmp_output:
      if manifest.data_schema.has_field(output_path):
        if overwrite:
          field = manifest.data_schema.get_field(output_path)
          if field.map is None and field.cluster is None:
            raise ValueError(
              f'{output_path} is not a map/cluster column and cannot be overwritten.'
            )
        elif input_path != output_path:
          raise ValueError(
            f'Cannot map to path "{output_path}" which already exists in the dataset. '
            'Use overwrite=True to overwrite the column.'
          )
    filters, _ = self._normalize_filters(
      filter_likes=filters, col_aliases={}, udf_aliases={}, manifest=self.manifest()
    )

    num_jobs = (os.cpu_count() or 1) if num_jobs == -1 else num_jobs
    pool_map = joblib.Parallel(n_jobs=num_jobs, return_as='generator', prefer=execution_type)

    jsonl_cache_filepath = _jsonl_cache_filepath(
      namespace=self.namespace,
      dataset_name=self.dataset_name,
      key=output_path,
      project_dir=self.project_dir,
      is_temporary=is_tmp_output,
    )

    sort_by = normalize_path(sort_by) if sort_by else None
    query_params = DuckDBQueryParams(
      filters=filters,
      limit=limit,
      include_deleted=include_deleted,
      sort_by=sort_by,
      sort_order=sort_order,
    )

    offset = self._get_cache_len(jsonl_cache_filepath, overwrite=overwrite)
    estimated_len = self.count(filters=filters, limit=limit, include_deleted=include_deleted)
    if task_id is not None:
      progress_bar = get_progress_bar(task_id, offset=offset, estimated_len=estimated_len)
    else:
      output_col_desc_suffix = f' to "{output_path}"' if output_path else ''
      progress_description = (
        f'[{self.namespace}/{self.dataset_name}][{num_jobs} shards] map '
        f'"{map_fn_name}"{output_col_desc_suffix}'
      )

      progress_bar = get_progress_bar(
        offset=offset,
        task_description=progress_description,
        estimated_len=estimated_len,
      )

    _consume_iterator(
      progress_bar(
        self._dispatch_workers(
          pool_map,
          map_fn,
          output_path,
          jsonl_cache_filepath,
          batch_size,
          input_path,
          overwrite=overwrite,
          query_options=query_params,
          resolve_span=resolve_span,
          embedding=embedding,
        ),
      )
    )

    json_schema: Optional[Schema] = None
    if output_path and schema:
      json_schema = create_json_map_output_schema(schema, output_path)

    json_query, map_schema, parquet_filepath = self._reshard_cache(
      manifest=manifest,
      output_path=output_path,
      jsonl_cache_filepaths=[jsonl_cache_filepath],
      schema=json_schema,
      is_tmp_output=is_tmp_output,
    )

    result = DuckDBMapOutput(con=self.con, query=json_query, output_path=output_path)

    if is_tmp_output:
      return result

    assert parquet_filepath is not None

    # Only add the map column if this map wasn't called by our clustering pipeline.
    if not schema or not schema.cluster:
      map_field_root = map_schema.get_field(output_path)
      map_source: str = ''
      try:
        map_source = inspect.getsource(map_fn)
      except Exception:
        pass
      map_field_root.map = MapInfo(
        fn_name=map_fn_name,
        input_path=input_path,
        fn_source=map_source,
        date_created=datetime.now(),
      )

    parquet_dir = os.path.dirname(parquet_filepath)
    prefix = '.'.join(output_path)
    map_manifest_filepath = os.path.join(parquet_dir, f'{prefix}.{MAP_MANIFEST_SUFFIX}')
    parquet_filename = os.path.basename(parquet_filepath)
    map_manifest = MapManifest(
      files=[parquet_filename],
      data_schema=map_schema,
      parquet_id=get_map_parquet_id(output_path),
      py_version=metadata.version('lilac'),
    )
    with open_file(map_manifest_filepath, 'w') as f:
      f.write(map_manifest.model_dump_json(exclude_none=True, indent=2))

    log(f'Wrote map output to {parquet_filename}')

    # Promote any new string columns as media fields if the length is above a threshold.
    for path, field in map_schema.leafs.items():
      if field.dtype in (STRING, STRING_SPAN):
        stats = self.stats(path, include_deleted=include_deleted)
        if stats.avg_text_length and stats.avg_text_length >= MEDIA_AVG_TEXT_LEN:
          self.add_media_field(path)

    return result

  @override
  def cluster(
    self,
    input: Union[Path, Callable[[Item], str], DatasetFormatInputSelector],
    output_path: Optional[Path] = None,
    min_cluster_size: int = 5,
    topic_fn: Optional[TopicFn] = cluster_titling.generate_title_openai,
    overwrite: bool = False,
    use_garden: bool = False,
    task_id: Optional[TaskId] = None,
    category_fn: Optional[TopicFn] = cluster_titling.generate_category_openai,
  ) -> None:
    topic_fn = topic_fn or cluster_titling.generate_title_openai
    category_fn = category_fn or cluster_titling.generate_category_openai
    return cluster_impl(
      self,
      input,
      output_path,
      min_cluster_size=min_cluster_size,
      topic_fn=topic_fn,
      category_fn=category_fn,
      overwrite=overwrite,
      use_garden=use_garden,
      task_id=task_id,
    )

  @override
  def to_huggingface(
    self,
    columns: Optional[Sequence[ColumnId]] = None,
    filters: Optional[Sequence[FilterLike]] = None,
    include_labels: Optional[Sequence[str]] = None,
    exclude_labels: Optional[Sequence[str]] = None,
    include_deleted: bool = False,
    include_signals: bool = False,
  ) -> HuggingFaceDataset:
    filters, _ = self._normalize_filters(
      filter_likes=filters, col_aliases={}, udf_aliases={}, manifest=self.manifest()
    )
    filters.extend(self._compile_include_exclude_filters(include_labels, exclude_labels))
    rows = self.select_rows(
      columns,
      filters=filters,
      combine_columns=True,
      include_deleted=include_deleted,
      exclude_signals=not include_signals,
    )

    def _gen() -> Iterator[Item]:
      for row in rows:
        yield row

    return cast(HuggingFaceDataset, HuggingFaceDataset.from_generator(_gen))

  @override
  def to_json(
    self,
    filepath: Union[str, pathlib.Path],
    jsonl: bool = True,
    columns: Optional[Sequence[ColumnId]] = None,
    filters: Optional[Sequence[FilterLike]] = None,
    include_labels: Optional[Sequence[str]] = None,
    exclude_labels: Optional[Sequence[str]] = None,
    include_deleted: bool = False,
    include_signals: bool = False,
  ) -> None:
    filters, _ = self._normalize_filters(
      filter_likes=filters, col_aliases={}, udf_aliases={}, manifest=self.manifest()
    )
    filters.extend(self._compile_include_exclude_filters(include_labels, exclude_labels))
    rows = self.select_rows(
      columns,
      filters=filters,
      combine_columns=True,
      include_deleted=include_deleted,
      exclude_signals=not include_signals,
    )
    filepath = os.path.expanduser(filepath)
    with open_file(filepath, 'wb') as file:
      if jsonl:
        for row in rows:
          file.write(orjson.dumps(row))
          file.write('\n'.encode('utf-8'))
      else:
        file.write(orjson.dumps(list(rows)))
    log(f'Dataset exported to {filepath}')

  @override
  def to_pandas(
    self,
    columns: Optional[Sequence[ColumnId]] = None,
    filters: Optional[Sequence[FilterLike]] = None,
    include_labels: Optional[Sequence[str]] = None,
    exclude_labels: Optional[Sequence[str]] = None,
    include_deleted: bool = False,
    include_signals: bool = False,
  ) -> pd.DataFrame:
    filters, _ = self._normalize_filters(
      filter_likes=filters, col_aliases={}, udf_aliases={}, manifest=self.manifest()
    )
    filters.extend(self._compile_include_exclude_filters(include_labels, exclude_labels))
    rows = self.select_rows(
      columns,
      filters=filters,
      combine_columns=True,
      include_deleted=include_deleted,
      exclude_signals=not include_signals,
    )
    return pd.DataFrame.from_records(list(rows))

  @override
  def to_csv(
    self,
    filepath: Union[str, pathlib.Path],
    columns: Optional[Sequence[ColumnId]] = None,
    filters: Optional[Sequence[FilterLike]] = None,
    include_labels: Optional[Sequence[str]] = None,
    exclude_labels: Optional[Sequence[str]] = None,
    include_deleted: bool = False,
    include_signals: bool = False,
  ) -> None:
    manifest = self.manifest()
    filters, _ = self._normalize_filters(
      filter_likes=filters, col_aliases={}, udf_aliases={}, manifest=manifest
    )
    filters.extend(self._compile_include_exclude_filters(include_labels, exclude_labels))
    select_schema = self.select_rows_schema(columns, combine_columns=True)
    rows = self.select_rows(
      columns,
      filters=filters,
      combine_columns=True,
      include_deleted=include_deleted,
      exclude_signals=not include_signals,
    )
    fieldnames = list(select_schema.data_schema.fields.keys())
    filepath = os.path.expanduser(filepath)
    with open_file(filepath, 'w') as file:
      writer = csv.DictWriter(file, fieldnames=fieldnames)
      writer.writeheader()
      writer.writerows(rows)
    log(f'Dataset exported to {filepath}')

  @override
  def to_parquet(
    self,
    filepath: Union[str, pathlib.Path],
    columns: Optional[Sequence[ColumnId]] = None,
    filters: Optional[Sequence[FilterLike]] = None,
    include_labels: Optional[Sequence[str]] = None,
    exclude_labels: Optional[Sequence[str]] = None,
    include_deleted: bool = False,
    include_signals: bool = False,
  ) -> None:
    filters, _ = self._normalize_filters(
      filter_likes=filters, col_aliases={}, udf_aliases={}, manifest=self.manifest()
    )
    filters.extend(self._compile_include_exclude_filters(include_labels, exclude_labels))
    select_schema = self.select_rows_schema(
      columns, combine_columns=True, exclude_signals=not include_signals
    )
    rows = self.select_rows(
      columns,
      filters=filters,
      combine_columns=True,
      include_deleted=include_deleted,
      exclude_signals=not include_signals,
    )
    filepath = os.path.expanduser(filepath)
    with open_file(filepath, 'wb') as f:
      writer = ParquetWriter(select_schema.data_schema)
      writer.open(f)
      for row in rows:
        writer.write(row)
      writer.close()

  def _assert_embedding_exists(self, path: PathTuple, embedding: str) -> None:
    manifest = self.manifest()
    embedding_path = (*path, embedding)
    if not manifest.data_schema.has_field(embedding_path):
      raise ValueError(f'Embedding "{embedding}" not found for path {path}.')

  def _inner_select(
    self,
    sub_paths: list[PathTuple],
    path: PathTuple,
    schema: Schema,
    inner_var: Optional[str] = None,
    empty: bool = False,
    span_from: Optional[PathTuple] = None,
  ) -> str:
    """Recursively generate the inner select statement for a list of sub paths."""
    current_sub_path = sub_paths[0]
    lambda_var = inner_var + 'x' if inner_var else 'x'
    if not inner_var:
      lambda_var = 'x'
      inner_var = escape_col_name(current_sub_path[0])
      current_sub_path = current_sub_path[1:]
    # Select the path inside structs. E.g. x['a']['b']['c'] given current_sub_path = [a, b, c].
    path_key = inner_var + ''.join([f'[{escape_string_literal(p)}]' for p in current_sub_path])
    if len(sub_paths) == 1:
      if span_from:
        duckdb_path = self._leaf_path_to_duckdb_path(span_from, schema)
        derived_col = self._select_sql(
          duckdb_path, flatten=False, unnest=False, path=path, schema=schema
        )
        path_key = (
          f'{derived_col}[{path_key}.{SPAN_KEY}.{TEXT_SPAN_START_FEATURE}+1:'
          f'{path_key}.{SPAN_KEY}.{TEXT_SPAN_END_FEATURE}]'
        )
      return 'NULL' if empty else path_key
    return (
      f'list_transform({path_key}, {lambda_var} -> '
      f'{self._inner_select(sub_paths[1:], path, schema, lambda_var, empty, span_from)})'
    )

  def _select_sql(
    self,
    sql_path: tuple[str, ...],
    flatten: bool,
    unnest: bool,
    path: PathTuple,
    schema: Schema,
    empty: bool = False,
    span_from: Optional[PathTuple] = None,
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
    selection = self._inner_select(sub_paths, path, schema, None, empty, span_from)
    # We only flatten when the result is a deeply nested list to avoid segfault.
    # The nesting list level is a func of subpaths, e.g. subPaths = [[a, b, c], *, *] is 2 levels.
    nesting_level = len(sub_paths) - 1

    # If the parent field is a map, accessing a key returns a list, which increases nesting level:
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

  def _add_searches_to_filters(
    self, searches: Sequence[Search], filters: list[Filter]
  ) -> list[Filter]:
    for search in searches:
      search_path = normalize_path(search.path)
      if search.type == 'keyword':
        filters.append(Filter(path=search_path, op='ilike', value=search.query))
      elif search.type == 'semantic' or search.type == 'concept':
        # Semantic search and concepts don't yet filter.
        continue
      elif search.type == 'metadata':
        # Make a regular filter query.
        filter = Filter(path=search_path, op=search.op, value=search.value)
        filters.append(filter)
      else:
        raise ValueError(f'Unknown search operator {search.type}.')
    return filters


def _escape_like_value(value: str) -> str:
  value = value.replace('%', '\\%').replace('_', '\\_')
  value = escape_string_literal(f'%{value}%')
  return f"{value} ESCAPE '\\'"


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


def read_source_manifest(dataset_path: str) -> SourceManifest:
  """Read the manifest file."""
  manifest_filepath = os.path.join(dataset_path, MANIFEST_FILENAME)
  if not os.path.exists(manifest_filepath):
    raise ValueError(
      f'Dataset manifest does not exist at path: {manifest_filepath}. '
      'Please check that the dataset name is correct and that you set the lilac project dir '
      'correctly. To set the project dir call: `ll.set_project_dir("path/to/project")`.'
    )
  # TODO(nsthorat): Overwrite the source manifest with a "source" added if the source is not defined
  # by reading the config yml.
  with open_file(manifest_filepath, 'r') as f:
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
    elif source_cell is None:
      return dest_cell
    else:
      return {VALUE_KEY: source_cell, **dest_cell}
  elif isinstance(dest_cell, list):
    if not isinstance(source_cell, list):
      raise ValueError('Failed to merge cells. Destination is a list, but source is not.')
    return [
      _merge_cells(dest_subcell, source_subcell)
      for dest_subcell, source_subcell in zip(dest_cell, source_cell)
    ]
  elif dest_cell is None:
    return source_cell
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
  path = tuple(column.path)
  while path[-1] == PATH_WILDCARD:
    path = path[:-1]
  return '.'.join(path)


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
      df[col] = df[col].replace(np.nan, None)
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


def _remove_signals_from_field(field: Field) -> Optional[Field]:
  """Remove signals from a field."""
  if field.signal is not None:
    return None

  if field.fields:
    fields: dict[str, Field] = {}
    for key, sub_field in field.fields.items():
      if sub_field and not sub_field.signal:
        sub_field_no_signals = _remove_signals_from_field(sub_field)
        if sub_field_no_signals:
          fields[key] = sub_field_no_signals
    return Field(fields=fields, dtype=field.dtype)

  if field.repeated_field:
    if not field.signal:
      sub_field_no_signals = _remove_signals_from_field(field.repeated_field)
      if sub_field_no_signals:
        return Field(repeated_field=sub_field_no_signals, dtype=field.dtype)
      else:
        return None
    else:
      return None

  return field


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


def _auto_bins(stats: StatsResult) -> list[Bin]:
  if stats.min_val is None or stats.max_val is None:
    return [('0', None, None)]

  if stats.min_val == stats.max_val:
    # Avoid division by zero when value_range = 0
    const_val = cast(float, stats.min_val)
    return [('0', const_val, None)]

  is_integer = stats.value_samples and all(isinstance(val, int) for val in stats.value_samples)
  def _round(value: float) -> float:
    # Select a round ndigits as a function of the value range. We offset it by 2 to allow for some
    # decimal places as a function of the range.
    if not value:
      return round(value)
    round_ndigits = -1 * round(math.log10(abs(value))) + 1
    if is_integer:
      round_ndigits = min(round_ndigits, 0)
    return round(value, round_ndigits)

  num_bins = min(int(np.log2(stats.total_count)), MAX_AUTO_BINS)
  transformer = PowerTransformer().fit(np.array(stats.value_samples).reshape(-1, 1))
  # [-2, 2], assuming post-transform normal distribution, should cover central 95% of the data.
  buckets = transformer.inverse_transform(np.linspace(-2.5, 2.5, num_bins).reshape(-1, 1)).ravel()
  # Sometimes the autogenerated buckets round to the same value.
  # Sometimes PowerTransformer returns NaN for some unusually shaped distributions.
  buckets = sorted(set(_round(val) for val in buckets if not np.isnan(val)))
  buckets = [None] + buckets + [None]
  bins = []
  for i, (start, end) in enumerate(zip(buckets[:-1], buckets[1:])):
    bins.append((str(i), start, end))

  return bins


def get_labels_sqlite_filename(dataset_output_dir: str, label_name: str) -> str:
  """Get the filepath to the labels file."""
  return os.path.join(dataset_output_dir, f'{label_name}{LABELS_SQLITE_SUFFIX}')
