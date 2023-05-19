"""The DuckDB implementation of the dataset database."""
import functools
import glob
import math
import os
import re
import threading
from typing import Any, Iterable, Iterator, Optional, Sequence, Type, Union, cast

import duckdb
import numpy as np
import pandas as pd
from pandas.api.types import is_object_dtype
from pydantic import BaseModel, validator
from typing_extensions import override

from ..concepts.db_concept import DISK_CONCEPT_MODEL_DB, ConceptModelDB
from ..config import CONFIG, data_path
from ..embeddings.vector_store import VectorStore
from ..embeddings.vector_store_numpy import NumpyVectorStore
from ..schema import (
  MANIFEST_FILENAME,
  PATH_WILDCARD,
  TEXT_SPAN_END_FEATURE,
  TEXT_SPAN_START_FEATURE,
  UUID_COLUMN,
  VALUE_KEY,
  DataType,
  Field,
  Item,
  ItemValue,
  Path,
  PathTuple,
  RichData,
  Schema,
  SignalInputType,
  SourceManifest,
  is_float,
  is_integer,
  is_ordinal,
  normalize_path,
  signal_compute_type_supports_dtype,
)
from ..signals.concept_scorer import ConceptScoreSignal
from ..signals.signal import (
  Signal,
  TextEmbeddingModelSignal,
  TextEmbeddingSignal,
  TextSignal,
  resolve_signal,
)
from ..tasks import TaskId, progress
from ..utils import DebugTimer, get_dataset_output_dir, log, open_file
from . import dataset
from .dataset import (
  BinaryOp,
  Bins,
  Column,
  ColumnId,
  Dataset,
  DatasetManifest,
  FeatureListValue,
  FeatureValue,
  Filter,
  FilterLike,
  FilterOp,
  GroupsSortBy,
  ListOp,
  MediaResult,
  NamedBins,
  SelectGroupsResult,
  SelectRowsResult,
  SelectRowsSchemaResult,
  SortOrder,
  StatsResult,
  UnaryOp,
  column_from_identifier,
  make_parquet_id,
)
from .dataset_utils import (
  count_primitives,
  create_signal_schema,
  flatten,
  flatten_keys,
  itemize_primitives,
  merge_schemas,
  read_embedding_index,
  replace_embeddings_with_none,
  schema_contains_path,
  unflatten,
  wrap_in_dicts,
  write_item_embeddings_to_disk,
  write_items_to_parquet,
)

DEBUG = CONFIG['DEBUG'] == 'true' if 'DEBUG' in CONFIG else False
UUID_INDEX_FILENAME = 'uuids.npy'

SIGNAL_MANIFEST_FILENAME = 'signal_manifest.json'
SOURCE_VIEW_NAME = 'source'

# Sample size for approximating the distinct count of a column.
SAMPLE_SIZE_DISTINCT_COUNT = 100_000

BINARY_OP_TO_SQL: dict[BinaryOp, str] = {
  BinaryOp.EQUALS: '=',
  BinaryOp.NOT_EQUAL: '!=',
  BinaryOp.GREATER: '>',
  BinaryOp.GREATER_EQUAL: '>=',
  BinaryOp.LESS: '<',
  BinaryOp.LESS_EQUAL: '<=',
}

SUPPORTED_OPS_ON_REPEATED: set[FilterOp] = set([UnaryOp.EXISTS])


class DuckDBSelectGroupsResult(SelectGroupsResult):
  """The result of a select groups query backed by DuckDB."""

  def __init__(self, df: pd.DataFrame) -> None:
    """Initialize the result."""
    self._df = df

  @override
  def __iter__(self) -> Iterator:
    return (tuple(row) for _, row in self._df.iterrows())

  @override
  def df(self) -> pd.DataFrame:
    """Convert the result to a pandas DataFrame."""
    return self._df


class DatasetDuckDB(Dataset):
  """The DuckDB implementation of the dataset database."""

  def __init__(
    self,
    namespace: str,
    dataset_name: str,
    vector_store_cls: Type[VectorStore] = NumpyVectorStore,
    concept_model_db: ConceptModelDB = DISK_CONCEPT_MODEL_DB,
  ):
    super().__init__(namespace, dataset_name)

    self.dataset_path = get_dataset_output_dir(data_path(), namespace, dataset_name)

    # TODO: Infer the manifest from the parquet files so this is lighter weight.
    self._source_manifest = read_source_manifest(self.dataset_path)
    self._signal_manifests: list[SignalManifest] = []
    self.con = duckdb.connect(database=':memory:')

    # Maps a column path and embedding to the vector store. This is lazily generated as needed.
    self._col_vector_stores: dict[PathTuple, VectorStore] = {}
    self.vector_store_cls = vector_store_cls
    self._concept_model_db = concept_model_db
    self._manifest_lock = threading.Lock()

  def _create_view(self, view_name: str, parquet_files: list[str]) -> None:
    self.con.execute(f"""
      CREATE OR REPLACE VIEW "{view_name}" AS (SELECT * FROM read_parquet({parquet_files}));
    """)

  @functools.cache
  # NOTE: This is cached, but when the latest mtime of any file in the dataset directory changes
  # the results are invalidated.
  def _recompute_joint_table(self, latest_mtime: float) -> DatasetManifest:
    del latest_mtime  # This is used as the cache key.
    merged_schema = self._source_manifest.data_schema.copy(deep=True)
    self._signal_manifests = []
    # Make a joined view of all the column groups.
    self._create_view(SOURCE_VIEW_NAME,
                      [os.path.join(self.dataset_path, f) for f in self._source_manifest.files])

    # Add the signal column groups.
    for root, _, files in os.walk(self.dataset_path):
      for file in files:
        if not file.endswith(SIGNAL_MANIFEST_FILENAME):
          continue

        with open_file(os.path.join(root, file)) as f:
          signal_manifest = SignalManifest.parse_raw(f.read())
        self._signal_manifests.append(signal_manifest)
        signal_files = [os.path.join(root, f) for f in signal_manifest.files]
        self._create_view(signal_manifest.parquet_id, signal_files)

    merged_schema = merge_schemas([self._source_manifest.data_schema] +
                                  [m.data_schema for m in self._signal_manifests])

    # The logic below generates the following example query:
    # CREATE OR REPLACE VIEW t AS (
    #   SELECT
    #     source.*,
    #     "parquet_id1"."root_column" AS "parquet_id1",
    #     "parquet_id2"."root_column" AS "parquet_id2"
    #   FROM source JOIN "parquet_id1" USING (uuid,) JOIN "parquet_id2" USING (uuid,)
    # );
    # NOTE: "root_column" for each signal is defined as the top-level column.
    select_sql = ', '.join([f'{SOURCE_VIEW_NAME}.*'] + [
      f'"{manifest.parquet_id}"."{_root_column(manifest)}" AS "{manifest.parquet_id}"'
      for manifest in self._signal_manifests
    ])
    join_sql = ' '.join([SOURCE_VIEW_NAME] + [
      f'join "{manifest.parquet_id}" using ({UUID_COLUMN},)' for manifest in self._signal_manifests
    ])

    sql_cmd = f"""CREATE OR REPLACE VIEW t AS (SELECT {select_sql} FROM {join_sql})"""
    self.con.execute(sql_cmd)

    # Get the total size of the table.
    size_query = 'SELECT COUNT() as count FROM t'
    size_query_result = cast(Any, self._query(size_query)[0])
    num_items = cast(int, size_query_result[0])

    return DatasetManifest(
      namespace=self.namespace,
      dataset_name=self.dataset_name,
      data_schema=merged_schema,
      num_items=num_items)

  @override
  def manifest(self) -> DatasetManifest:
    # Use the latest modification time of all files under the dataset path as the cache key for
    # re-computing the manifest and the joined view.
    all_dataset_files = glob.iglob(os.path.join(self.dataset_path, '**'), recursive=True)
    latest_mtime = max(map(os.path.getmtime, all_dataset_files))
    with self._manifest_lock:
      return self._recompute_joint_table(latest_mtime)

  def count(self, filters: Optional[list[FilterLike]] = None) -> int:
    """Count the number of rows."""
    raise NotImplementedError('count is not yet implemented for DuckDB.')

  def _get_vector_store(self, path: PathTuple) -> VectorStore:
    if path not in self._col_vector_stores:
      manifest = next(
        m for m in self._signal_manifests if schema_contains_path(m.data_schema, path))
      if not manifest:
        raise ValueError(f'No embedding found for path {path}.')
      if not manifest.embedding_filename:
        raise ValueError(f'Signal manifest for path {path} is not an embedding. '
                         f'Got signal manifest: {manifest}')

      filepath = os.path.join(self.dataset_path, _signal_dir(manifest.enriched_path),
                              manifest.embedding_filename)
      embedding_index = read_embedding_index(filepath)
      # Get all the embeddings and pass it to the vector store.
      vector_store = self.vector_store_cls()
      vector_store.add(embedding_index.keys, embedding_index.embeddings)
      # Cache the vector store.
      self._col_vector_stores[path] = vector_store

    return self._col_vector_stores[path]

  def _prepare_signal(self,
                      signal: Signal,
                      source_path: PathTuple,
                      compute_dependencies: Optional[bool] = False,
                      task_id: Optional[TaskId] = None) -> PathTuple:
    """Run all the signals depedencies required to run this signal.

    Args:
      signal: The signal to prepare.
      source_path: The source path the signal is running over.
      compute_dependencies: If True, signals will get computed for the whole column. If False,
        throw if the required inputs are not computed yet.
      task_id: The TaskId used to run the signal.

    Returns
      The final path the signal will be run over.
    """
    is_value_path = False
    if source_path[-1] == VALUE_KEY:
      is_value_path = True
      source_path = source_path[:-1]

    new_path = source_path

    if isinstance(signal, TextSignal):
      split_signal = signal.get_split_signal()
      if split_signal:
        new_path = (*new_path, split_signal.key(), PATH_WILDCARD)
        if new_path not in self.manifest().data_schema.leafs:
          if compute_dependencies:
            self.compute_signal(split_signal, source_path, task_id=task_id)
          else:
            raise ValueError(f'Split signal "{split_signal.key()}" is not computed. '
                             f'Please run `dataset.compute_signal` over {source_path} first.')

      if isinstance(signal, TextEmbeddingModelSignal):
        embedding_signal = signal.get_embedding_signal()
        if embedding_signal:
          new_path = (*new_path, embedding_signal.key())
          if new_path not in self.manifest().data_schema.leafs:
            if compute_dependencies:
              self.compute_signal(embedding_signal, source_path, task_id=task_id)
            else:
              raise ValueError(f'Embedding signal "{embedding_signal.key()}" is not computed over '
                               f'{source_path}. Please run `dataset.compute_signal` over '
                               f'{source_path} first.')

    if is_value_path:
      new_path = (*new_path, VALUE_KEY)
    return new_path

  @override
  def compute_signal(self,
                     signal: Signal,
                     column: ColumnId,
                     task_id: Optional[TaskId] = None) -> None:
    source_path = column_from_identifier(column).path

    # Prepare the dependencies of this signal.
    signal_source_path = self._prepare_signal(signal, source_path, compute_dependencies=True)

    signal_col = Column(path=source_path, alias='value', signal_udf=signal)
    select_rows_result = self.select_rows([signal_col], task_id=task_id, resolve_span=True)
    df = select_rows_result.df()
    values = df['value']

    source_path = signal_source_path
    signal_col.path = source_path

    enriched_path = _col_destination_path(signal_col)
    spec = _split_path_into_subpaths_of_lists(enriched_path)
    output_dir = os.path.join(self.dataset_path, _signal_dir(enriched_path))
    signal_schema = create_signal_schema(signal, source_path, self.manifest().data_schema)
    enriched_signal_items = cast(Iterable[Item], wrap_in_dicts(values, spec))
    for uuid, item in zip(df[UUID_COLUMN], enriched_signal_items):
      item[UUID_COLUMN] = uuid

    is_embedding = isinstance(signal, TextEmbeddingSignal)
    embedding_filename = None
    if is_embedding:
      embedding_filename = os.path.basename(
        write_item_embeddings_to_disk(
          keys=df[UUID_COLUMN],
          embeddings=values,
          output_dir=output_dir,
          shard_index=0,
          num_shards=1))

      # Replace the embeddings with None so they are not serialized in the parquet file.
      enriched_signal_items = (replace_embeddings_with_none(item) for item in enriched_signal_items)

    enriched_signal_items = list(enriched_signal_items)
    parquet_filename, _ = write_items_to_parquet(
      items=enriched_signal_items,
      output_dir=output_dir,
      schema=signal_schema,
      filename_prefix='data',
      shard_index=0,
      num_shards=1,
      # The result of select_rows with a signal udf has already wrapped primitive values.
      dont_wrap_primitives=True)

    signal_manifest = SignalManifest(
      files=[parquet_filename],
      data_schema=signal_schema,
      signal=signal,
      enriched_path=source_path,
      parquet_id=make_parquet_id(signal, source_path),
      embedding_filename=embedding_filename)
    signal_manifest_filepath = os.path.join(output_dir, SIGNAL_MANIFEST_FILENAME)
    with open_file(signal_manifest_filepath, 'w') as f:
      f.write(signal_manifest.json(exclude_none=True, indent=2))
    log(f'Wrote signal manifest to {signal_manifest_filepath}')

  def _validate_filters(self, filters: Sequence[Filter], col_aliases: dict[str, PathTuple]) -> None:
    manifest = self.manifest()
    for filter in filters:
      if filter.path[0] in col_aliases:
        # This is a filter on a column alias, which is always allowed.
        continue

      current_field = Field(fields=manifest.data_schema.fields)
      for path_part in filter.path:
        if path_part == VALUE_KEY:
          if not current_field.dtype:
            raise ValueError(f'Unable to filter on path {filter.path}. The field has no value.')
          continue
        if current_field.fields:
          if path_part not in current_field.fields:
            raise ValueError(f'Unable to filter on path {filter.path}. '
                             f'Path part "{path_part}" not found in the dataset.')
          current_field = current_field.fields[str(path_part)]
          continue
        elif current_field.repeated_field:
          if (filter.op not in SUPPORTED_OPS_ON_REPEATED and not path_part.isdigit()):
            raise ValueError(f'Unable to filter on path {filter.path}. '
                             'Filtering must be on a specific index of a repeated field')
          current_field = current_field.repeated_field
          continue
        else:
          raise ValueError(f'Unable to filter on path {filter.path}. '
                           f'Path part "{path_part}" is not defined on a primitive value.')

  def _validate_columns(self, columns: Sequence[Column], schema: Schema) -> None:
    for column in columns:
      if column.signal_udf:
        path = column.path

        # Signal transforms must operate on a leaf field.
        leaf = schema.leafs.get(path)
        if not leaf or not leaf.dtype:
          raise ValueError(f'Leaf "{path}" not found in dataset. '
                           'Signal transforms must operate on a leaf field.')

        # Signal transforms must have the same dtype as the leaf field.
        signal = column.signal_udf
        compute_type = signal.compute_type

        if not signal_compute_type_supports_dtype(compute_type, leaf.dtype):
          raise ValueError(f'Leaf "{path}" has dtype "{leaf.dtype}" which is not supported '
                           f'by "{signal.key()}" with signal input type "{compute_type}".')

        # Select the value key from duckdb as this gives us the value for the leaf field, allowing
        # us to remove python code that unwraps the value key before calling the signal.
        column.path = _make_value_path(column.path)

      current_field = Field(fields=schema.fields)
      path = column.path
      for path_part in path:
        if path_part == VALUE_KEY:
          if not current_field.dtype:
            raise ValueError(f'Unable to select path {path}. The field that has no value.')
          continue
        if current_field.fields:
          if path_part not in current_field.fields:
            raise ValueError(f'Unable to select path {path}. '
                             f'Path part "{path_part}" not found in the dataset.')
          current_field = current_field.fields[path_part]
          continue
        elif current_field.repeated_field:
          if path_part.isdigit():
            raise ValueError(f'Unable to select path {path}. Selecting a specific index of '
                             'a repeated field is currently not supported.')
          if path_part != PATH_WILDCARD:
            raise ValueError(f'Unable to select path {path}. '
                             f'Path part "{path_part}" should be a wildcard.')
          current_field = current_field.repeated_field
        elif not current_field.dtype:
          raise ValueError(f'Unable to select path {path}. '
                           f'Path part "{path_part}" is not defined on a primitive value.')

  def _validate_sort_path(self, path: PathTuple, schema: Schema) -> None:
    current_field = Field(fields=schema.fields)
    for path_part in path:
      if path_part == VALUE_KEY:
        if not current_field.dtype:
          raise ValueError(f'Unable to sort by path {path}. The field that has no value.')
        continue
      if current_field.fields:
        if path_part not in current_field.fields:
          raise ValueError(f'Unable to sort by path {path}. '
                           f'Path part "{path_part}" not found in the dataset.')
        current_field = current_field.fields[path_part]
        continue
      elif current_field.repeated_field:
        if path_part.isdigit():
          raise ValueError(f'Unable to sort by path {path}. Selecting a specific index of '
                           'a repeated field is currently not supported.')
        if path_part != PATH_WILDCARD:
          raise ValueError(f'Unable to sort by path {path}. '
                           f'Path part "{path_part}" should be a wildcard.')
        current_field = current_field.repeated_field
      elif not current_field.dtype:
        raise ValueError(f'Unable to sort by path {path}. '
                         f'Path part "{path_part}" is not defined on a primitive value.')

  @override
  def stats(self, leaf_path: Path) -> StatsResult:
    if not leaf_path:
      raise ValueError('leaf_path must be provided')
    path = normalize_path(leaf_path)
    manifest = self.manifest()
    leafs = manifest.data_schema.leafs
    leaf = manifest.data_schema.leafs.get(path)
    if not leaf or not leaf.dtype:
      raise ValueError(f'Leaf "{path}" not found in dataset')

    value_path = _make_value_path(path)
    duckdb_path = self._leaf_path_to_duckdb_path(value_path)
    inner_select = _select_sql(
      duckdb_path, flatten=True, unnest=True, span_from=self._get_span_from(path))

    # Compute approximate count by sampling the data to avoid OOM.
    sample_size = SAMPLE_SIZE_DISTINCT_COUNT
    avg_length_query = ''
    if leaf.dtype == DataType.STRING:
      avg_length_query = ', avg(length(val)) as avgTextLength'

    approx_count_query = f"""
      SELECT approx_count_distinct(val) as approxCountDistinct {avg_length_query}
      FROM (SELECT {inner_select} AS val FROM t LIMIT {sample_size});
    """
    row = self._query(approx_count_query)[0]
    approx_count_distinct = row[0]

    total_count_query = f'SELECT count(val) FROM (SELECT {inner_select} as val FROM t)'
    total_count = self._query(total_count_query)[0][0]

    # Adjust the counts for the sample size.
    factor = max(1, total_count / sample_size)
    approx_count_distinct = round(approx_count_distinct * factor)

    result = StatsResult(total_count=total_count, approx_count_distinct=approx_count_distinct)

    if leaf.dtype == DataType.STRING:
      result.avg_text_length = row[1]

    # Compute min/max values for ordinal leafs, without sampling the data.
    if is_ordinal(leaf.dtype):
      min_max_query = f"""
        SELECT MIN(val) AS minVal, MAX(val) AS maxVal
        FROM (SELECT {inner_select} as val FROM t);
      """
      row = self._query(min_max_query)[0]
      result.min_val, result.max_val = row

    return result

  @override
  def select_groups(self,
                    leaf_path: Path,
                    filters: Optional[Sequence[FilterLike]] = None,
                    sort_by: Optional[GroupsSortBy] = GroupsSortBy.COUNT,
                    sort_order: Optional[SortOrder] = SortOrder.DESC,
                    limit: Optional[int] = None,
                    bins: Optional[Bins] = None) -> SelectGroupsResult:
    if not leaf_path:
      raise ValueError('leaf_path must be provided')
    path = normalize_path(leaf_path)
    manifest = self.manifest()
    leaf = manifest.data_schema.leafs.get(path)
    if not leaf or not leaf.dtype:
      raise ValueError(f'Leaf "{path}" not found in dataset')

    stats = self.stats(leaf_path)
    if not bins and stats.approx_count_distinct >= dataset.TOO_MANY_DISTINCT:
      raise ValueError(f'Leaf "{path}" has too many unique values: {stats.approx_count_distinct}')

    inner_val = 'inner_val'
    outer_select = inner_val
    if is_float(leaf.dtype) or is_integer(leaf.dtype):
      if bins is None:
        raise ValueError(f'"bins" needs to be defined for the int/float leaf "{path}"')
      # Normalize the bins to be `NamedBins`.
      named_bins = bins if isinstance(bins, NamedBins) else NamedBins(bins=bins)
      bounds = []
      # Normalize the bins to be in the form of (label, bound).

      for i in range(len(named_bins.bins) + 1):
        prev = named_bins.bins[i - 1] if i > 0 else "'-Infinity'"
        next = named_bins.bins[i] if i < len(named_bins.bins) else "'Infinity'"
        label = f"'{named_bins.labels[i]}'" if named_bins.labels else i
        bounds.append(f'({label}, {prev}, {next})')
      bin_index_col = 'col0'
      bin_min_col = 'col1'
      bin_max_col = 'col2'
      # We cast the field to `double` so bining works for both `float` and `int` fields.
      outer_select = f"""(
        SELECT {bin_index_col} FROM (
          VALUES {', '.join(bounds)}
        ) WHERE {inner_val}::DOUBLE >= {bin_min_col} AND {inner_val}::DOUBLE < {bin_max_col}
      )"""
    count_column = 'count'
    value_column = 'value'

    limit_query = f'LIMIT {limit}' if limit else ''
    # Select the actual value from the node.
    value_path = _make_value_path(path)
    inner_select = _select_sql(value_path, flatten=True, unnest=True)
    query = f"""
      SELECT {outer_select} AS {value_column}, COUNT() AS {count_column}
      FROM (SELECT {inner_select} AS {inner_val} FROM t)
      GROUP BY {value_column}
      ORDER BY {sort_by} {sort_order}
      {limit_query}
    """
    return DuckDBSelectGroupsResult(self._query_df(query))

  def _sorting_by_topk_of_signal(self, limit: Optional[int], sort_order: Optional[SortOrder],
                                 sort_cols_after_udf: list[str], signal_column: str) -> bool:
    """Returns True if the query is sorting by the topk of a signal column."""
    return bool(limit and sort_order == SortOrder.DESC and sort_cols_after_udf and
                self._path_to_col(signal_column) == sort_cols_after_udf[0])

  def _normalize_columns(self, columns: Optional[Sequence[ColumnId]],
                         schema: Schema) -> list[Column]:
    """Normalizes the columns to a list of `Column` objects."""
    cols = [column_from_identifier(col) for col in columns or []]
    star_in_cols = any(col.path == ('*',) for col in cols)
    if not cols or star_in_cols:
      # Select all columns.
      cols.extend([Column(name) for name in schema.fields.keys()])
      if star_in_cols:
        cols = [col for col in cols if col.path != ('*',)]
    return cols

  @override
  def select_rows(self,
                  columns: Optional[Sequence[ColumnId]] = None,
                  filters: Optional[Sequence[FilterLike]] = None,
                  sort_by: Optional[Sequence[Path]] = None,
                  sort_order: Optional[SortOrder] = SortOrder.DESC,
                  limit: Optional[int] = None,
                  offset: Optional[int] = 0,
                  task_id: Optional[TaskId] = None,
                  resolve_span: bool = False,
                  combine_columns: bool = False) -> SelectRowsResult:
    manifest = self.manifest()
    cols = self._normalize_columns(columns, manifest.data_schema)

    # Always return the UUID column.
    col_paths = [col.path for col in cols]
    if (UUID_COLUMN,) not in col_paths:
      cols.append(column_from_identifier(UUID_COLUMN))

    # Prepare UDF columns. Throw an error if they are not computed. Update the paths of the UDFs so
    # they match the paths of the columns defined by splits and embeddings.
    for col in cols:
      if col.signal_udf:
        # Do not auto-compute dependencies, throw an error if they are not computed.
        col.path = self._prepare_signal(col.signal_udf, col.path, compute_dependencies=False)

    self._validate_columns(cols, manifest.data_schema)

    # Map a final column name to a list of temporary namespaced column names that need to be merged.
    columns_to_merge: dict[str, dict[str, Column]] = {}
    temp_column_to_offset_column: dict[str, tuple[str, Field]] = {}
    select_queries: list[str] = []

    for column in cols:
      path = column.path
      # If the signal is vector-based, we don't need to select the actual data, just the uuids
      # plus an arbitrarily nested array of `None`s`.
      empty = bool(
        column.signal_udf and
        # We remove the last element of the path when checking the dtype because it's VALUE_KEY for
        # signal transforms.
        manifest.data_schema.get_field(path[:-1]).dtype == DataType.EMBEDDING)

      select_sqls: list[str] = []
      final_col_name = column.alias or _unique_alias(column)
      if final_col_name not in columns_to_merge:
        columns_to_merge[final_col_name] = {}

      duckdb_paths = self._column_to_duckdb_paths(column)
      span_from = self._get_span_from(path) if resolve_span or column.signal_udf else None

      for parquet_id, duckdb_path in duckdb_paths:
        sql = _select_sql(
          duckdb_path, flatten=False, unnest=False, empty=empty, span_from=span_from)
        temp_column_name = (
          final_col_name if len(duckdb_paths) == 1 else f'{final_col_name}/{parquet_id}')
        select_sqls.append(f'{sql} AS "{temp_column_name}"')
        columns_to_merge[final_col_name][temp_column_name] = column

        if column.signal_udf and span_from and _schema_has_spans(column.signal_udf.fields()):
          sql = _select_sql(duckdb_path, flatten=False, unnest=False, empty=empty, span_from=None)
          temp_offset_column_name = f'{temp_column_name}/offset'
          select_sqls.append(f'{sql} AS "{temp_offset_column_name}"')
          temp_column_to_offset_column[temp_column_name] = (temp_offset_column_name,
                                                            column.signal_udf.fields())

      select_queries.append(', '.join(select_sqls))

    col_aliases: dict[str, PathTuple] = {col.alias: col.path for col in cols if col.alias}
    udf_aliases: dict[str, PathTuple] = {
      col.alias: col.path for col in cols if col.signal_udf and col.alias
    }

    # Filtering.
    where_query = ''
    filters, udf_filters = self._normalize_filters(filters, col_aliases, udf_aliases)
    filter_queries = self._create_where(filters)
    if filter_queries:
      where_query = f"WHERE {' AND '.join(filter_queries)}"

    # Sorting.
    order_query = ''
    sort_by = cast(list[PathTuple], [normalize_path(path) for path in (sort_by or [])])
    if sort_by and not sort_order:
      raise ValueError('`sort_order` is required when `sort_by` is specified.')

    sort_cols_before_udf: list[str] = []
    sort_cols_after_udf: list[str] = []

    for path in sort_by:
      # We only allow sorting by nodes with a value.
      path = _make_value_path(path)
      first_subpath = str(path[0])
      rest_of_path = path[1:]
      udf_path = udf_aliases.get(first_subpath)
      # UDF selection is slightly different than normal selection since the UDF column is already
      # present as a top-level column in the table.
      if udf_path:
        # If the user selected udf(document.*.text) as "udf" and wanted to sort by "udf.len", we
        # need to actually sort by "udf.*.len.__value__" where the "*" came from the fact that the
        # udf was applied to a list of "text" fields.
        prefix_path = [subpath for subpath in udf_path if subpath == PATH_WILDCARD]
        path = (first_subpath, *prefix_path, *rest_of_path)
      else:
        # Re-route the path if it starts with an alias by pointing it to the actual path.
        if first_subpath in col_aliases:
          path = (*col_aliases[first_subpath], *rest_of_path)

        self._validate_sort_path(path, manifest.data_schema)
        path = self._leaf_path_to_duckdb_path(cast(PathTuple, path))

      sort_col = _select_sql(path, flatten=True, unnest=False)
      has_repeated_field = any(subpath == PATH_WILDCARD for subpath in path)
      if has_repeated_field:
        sort_col = (f'list_min({sort_col})'
                    if sort_order == SortOrder.ASC else f'list_max({sort_col})')

      # Separate sort columns into two groups: those that need to be sorted before and after UDFs.
      if udf_path:
        sort_cols_after_udf.append(sort_col)
      else:
        sort_cols_before_udf.append(sort_col)

    if sort_cols_before_udf:
      order_query = (f'ORDER BY {", ".join(sort_cols_before_udf)} '
                     f'{cast(SortOrder, sort_order).value}')

    con = self.con.cursor()
    query = con.sql(f"""
      SELECT {', '.join(select_queries)} FROM t
      {where_query}
      {order_query}
    """)

    if limit and not sort_cols_after_udf:
      query = query.limit(limit, offset or 0)

    # Download the data so we can run UDFs on it in Python.
    df = _replace_nan_with_none(query.df())

    already_sorted = False

    # Run UDFs on the transformed columns.
    udf_columns = [col for col in cols if col.signal_udf]
    for udf_col in udf_columns:
      signal = cast(Signal, udf_col.signal_udf)

      if isinstance(signal, ConceptScoreSignal):
        # Make sure the model is in sync.
        concept_model = self._concept_model_db.get(signal.namespace, signal.concept_name,
                                                   signal.embedding)
        self._concept_model_db.sync(concept_model)

      signal_alias = udf_col.alias or _unique_alias(udf_col)
      temp_signal_cols = columns_to_merge[signal_alias]
      if len(temp_signal_cols) != 1:
        raise ValueError(
          f'Unable to compute signal {signal.name}. Signal UDFs only operate on leafs, but got '
          f'{len(temp_signal_cols)} underlying columns that contain data related to {udf_col.path}.'
        )
      signal_column = list(temp_signal_cols.keys())[0]
      input = df[signal_column]

      with DebugTimer(f'Computing signal "{signal}"'):
        if signal.compute_type in [SignalInputType.TEXT_EMBEDDING]:
          # The input is an embedding.
          vector_store = self._get_vector_store(udf_col.path)

          # If we are sorting by the topk of a signal column, we can utilize the vector store
          # via `signal.vector_compute_topk` and then use the topk to filter the dataframe. This
          # is much faster than computing the signal for all rows and then sorting.
          if self._sorting_by_topk_of_signal(limit, sort_order, sort_cols_after_udf, signal_column):
            already_sorted = True
            k = (limit or 0) + (offset or 0)
            topk = signal.vector_compute_topk(k, vector_store)
            unique_uuids = list(dict.fromkeys([key[0] for key, _ in topk]))
            df.set_index(UUID_COLUMN, drop=False, inplace=True)
            # Filter the dataframe by uuids that have at least one value in top k.
            df = df.loc[unique_uuids]
            for key, score in topk:
              # Walk a deep nested array and put the score at the right location.
              deep_array = df[signal_column]
              for key_part in key[:-1]:
                deep_array = deep_array[key_part]
              deep_array[key[-1]] = score
          else:
            flat_keys = flatten_keys(df[UUID_COLUMN], input)
            signal_out = signal.vector_compute(flat_keys, vector_store)
            # Add progress.
            if task_id is not None:
              signal_out = progress(signal_out, task_id=task_id, estimated_len=len(flat_keys))
            df[signal_column] = itemize_primitives(unflatten(signal_out, input))
        else:
          num_rich_data = count_primitives(input)
          flat_input = cast(Iterable[RichData], flatten(input))
          signal_out = signal.compute(flat_input)
          # Add progress.
          if task_id is not None:
            signal_out = progress(signal_out, task_id=task_id, estimated_len=num_rich_data)
          signal_out = list(signal_out)

          if signal_column in temp_column_to_offset_column:
            offset_column_name, schema = temp_column_to_offset_column[signal_column]
            nested_spans: Iterable[Item] = df[offset_column_name]
            flat_spans = list(flatten(nested_spans))
            for span, item in zip(flat_spans, signal_out):
              _offset_any_span(cast(int, span['start']), item, schema)

          if len(signal_out) != num_rich_data:
            raise ValueError(
              f'The signal generated {len(signal_out)} values but the input data had '
              f"{num_rich_data} values. This means the signal either didn't generate a "
              '"None" for a sparse output, or generated too many items.')

          df[signal_column] = itemize_primitives(unflatten(signal_out, input))

    if udf_filters or sort_cols_after_udf:
      # Re-upload the udf outputs to duckdb so we can filter/sort on them.
      query = con.from_df(df)

      if udf_filters:
        udf_filter_queries = self._create_where(udf_filters)
        if udf_filter_queries:
          query = query.filter(' AND '.join(udf_filter_queries))

      if not already_sorted and sort_cols_after_udf:
        if not sort_order:
          raise ValueError('`sort_order` is required when `sort_by` is specified.')
        query = query.order(f'{", ".join(sort_cols_after_udf)} {sort_order.value}')

      if limit:
        query = query.limit(limit, offset or 0)

      df = _replace_nan_with_none(query.df())

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
          df[temp_col_name] = wrap_in_dicts(df[temp_col_name], spec)

        # If the temp col name is the same as the final name, we can skip merging. This happens when
        # we select a source leaf column.
        if temp_col_name == final_col_name:
          continue

        if final_col_name not in df:
          df[final_col_name] = df[temp_col_name]
        else:
          df[final_col_name] = merge_values(df[final_col_name], df[temp_col_name])
        del df[temp_col_name]

    con.close()

    if combine_columns:
      # Since we aliased every column to `*`, the object with have only '*' as the key. We need to
      # elevate the all the columns under '*'.
      df = pd.DataFrame.from_records(df['*'])

    return SelectRowsResult(df)

  @override
  def select_rows_schema(self,
                         columns: Optional[Sequence[ColumnId]] = None,
                         combine_columns: bool = False) -> SelectRowsSchemaResult:
    """Returns the schema of the result of `select_rows` above with the same arguments."""
    if not combine_columns:
      raise NotImplementedError(
        'select_rows_schema with combine_columns=False is not yet supported.')
    manifest = self.manifest()
    cols = self._normalize_columns(columns, manifest.data_schema)
    # Always return the UUID column.
    col_paths = [col.path for col in cols]
    if (UUID_COLUMN,) not in col_paths:
      cols.append(column_from_identifier(UUID_COLUMN))

    # Prepare UDF columns. Throw an error if they are not computed. Update the paths of the UDFs so
    # they match the paths of the columns defined by splits and embeddings.
    for col in cols:
      if col.signal_udf:
        # Do not auto-compute dependencies, throw an error if they are not computed.
        col.path = self._prepare_signal(col.signal_udf, col.path, compute_dependencies=False)

    self._validate_columns(cols, manifest.data_schema)

    alias_udf_paths: dict[str, PathTuple] = {}
    col_schemas: list[Schema] = []
    for col in cols:
      dest_path = _col_destination_path(col)
      if col.signal_udf:
        if col.alias:
          alias_udf_paths[col.alias] = dest_path
        field = col.signal_udf.fields()
        field.signal = col.signal_udf.dict()
      else:
        field = self.manifest().data_schema.get_field(dest_path)
      col_schemas.append(_make_schema_from_path(dest_path, field))
    data_schema = merge_schemas(col_schemas)
    return SelectRowsSchemaResult(data_schema=data_schema, alias_udf_paths=alias_udf_paths)

  @override
  def media(self, item_id: str, leaf_path: Path) -> MediaResult:
    raise NotImplementedError('Media is not yet supported for the DuckDB implementation.')

  def _get_span_from(self, path: PathTuple) -> Optional[PathTuple]:
    manifest = self.manifest()
    leafs = manifest.data_schema.leafs
    # Remove the value key so we can check the dtype from leafs.
    span_path = path[:-1] if path[-1] == VALUE_KEY else path
    is_span = (span_path in leafs and leafs[span_path].dtype == DataType.STRING_SPAN)
    return _derived_from_path(path, manifest.data_schema) if is_span else None

  def _leaf_path_to_duckdb_path(self, leaf_path: PathTuple) -> PathTuple:
    ((_, duckdb_path),) = self._column_to_duckdb_paths(Column(leaf_path))
    return duckdb_path

  def _column_to_duckdb_paths(self, column: Column) -> list[tuple[str, PathTuple]]:
    path = column.path
    parquet_manifests: list[Union[SourceManifest, SignalManifest]] = [
      self._source_manifest, *self._signal_manifests
    ]
    duckdb_paths: list[tuple[str, PathTuple]] = []

    for m in parquet_manifests:
      if not schema_contains_path(m.data_schema, path):
        # Skip this parquet file if it doesn't contain the path.
        continue

      if isinstance(m, SignalManifest) and path == (UUID_COLUMN,):
        # Do not select UUID from the signal because it's already in the source.
        continue

      duckdb_path = path
      parquet_id = 'source'

      if isinstance(m, SignalManifest):
        duckdb_path = (m.parquet_id, *path[1:])
        parquet_id = m.parquet_id

      duckdb_paths.append((parquet_id, duckdb_path))

    if not duckdb_paths:
      raise ValueError(f'Invalid path "{path}": No manifest contains path. Valid paths: '
                       f'{list(self.manifest().data_schema.leafs.keys())}')

    return duckdb_paths

  def _normalize_filters(self, filter_likes: Optional[Sequence[FilterLike]],
                         col_aliases: dict[str, PathTuple],
                         udf_aliases: dict[str, PathTuple]) -> tuple[list[Filter], list[Filter]]:
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

      # We only allow filtering by nodes with a value.
      filter.path = _make_value_path(filter.path)

      if str(filter.path[0]) in udf_aliases:
        udf_filters.append(filter)
      else:
        filters.append(filter)

    self._validate_filters(filters, col_aliases)
    return filters, udf_filters

  def _create_where(self, filters: list[Filter]) -> list[str]:
    if not filters:
      return []
    filter_queries: list[str] = []
    binary_ops = set(BinaryOp)
    unary_ops = set(UnaryOp)
    list_ops = set(ListOp)
    for filter in filters:
      duckdb_path = self._leaf_path_to_duckdb_path(filter.path)
      select_str = _select_sql(duckdb_path, flatten=False, unnest=False)

      if filter.op in binary_ops:
        op = BINARY_OP_TO_SQL[cast(BinaryOp, filter.op)]
        filter_val = cast(FeatureValue, filter.value)
        if isinstance(filter_val, str):
          filter_val = f"'{filter_val}'"
        elif isinstance(filter_val, bytes):
          filter_val = _bytes_to_blob_literal(filter_val)
        else:
          filter_val = str(filter_val)
        filter_query = f'{select_str} {op} {filter_val}'
      elif filter.op in unary_ops:
        is_array = any(subpath == PATH_WILDCARD for subpath in filter.path)
        if filter.op == UnaryOp.EXISTS:
          filter_query = f'len({select_str}) > 0' if is_array else f'{select_str} IS NOT NULL'
        else:
          raise ValueError(f'Unary op: {filter.op} is not yet supported')
      elif filter.op in list_ops:
        if filter.op == ListOp.IN:
          filter_list_val = cast(FeatureListValue, filter.value)
          if not isinstance(filter_list_val, list):
            raise ValueError('filter with array value can only use the IN comparison')
          wrapped_filter_val = [f"'{part}'" for part in filter_list_val]
          filter_val = f'({", ".join(wrapped_filter_val)})'
          filter_query = f'{select_str} IN {filter_val}'
      else:
        raise ValueError(f'Invalid filter op: {filter.op}')
      filter_queries.append(filter_query)
    return filter_queries

  def _execute(self, query: str) -> duckdb.DuckDBPyConnection:
    """Execute a query in duckdb."""
    # FastAPI is multi-threaded so we have to create a thread-specific connection cursor to allow
    # these queries to be thread-safe.
    local_con = self.con.cursor()
    if not DEBUG:
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
    """Execute a query that returns a dataframe."""
    result = self._execute(query)
    df = _replace_nan_with_none(result.df())
    result.close()
    return df

  def _path_to_col(self, path: Path, quote_each_part: bool = True) -> str:
    """Convert a path to a column name."""
    if isinstance(path, str):
      path = (path,)
    return '.'.join([f'"{path_comp}"' if quote_each_part else str(path_comp) for path_comp in path])


def _inner_select(sub_paths: list[PathTuple],
                  inner_var: Optional[str] = None,
                  empty: bool = False,
                  span_from: Optional[PathTuple] = None) -> str:
  """Recursively generate the inner select statement for a list of sub paths."""
  current_sub_path = sub_paths[0]
  lambda_var = inner_var + 'x' if inner_var else 'x'
  if not inner_var:
    lambda_var = 'x'
    inner_var = f'"{current_sub_path[0]}"'
    current_sub_path = current_sub_path[1:]
  # Select the path inside structs. E.g. x['a']['b']['c'] given current_sub_path = [a, b, c].
  path_key = inner_var + ''.join([f"['{p}']" for p in current_sub_path])
  if len(sub_paths) == 1:
    if span_from:
      derived_col = _select_sql(span_from, flatten=False, unnest=False)
      path_key = (f'{derived_col}[{path_key}.{TEXT_SPAN_START_FEATURE}+1:'
                  f'{path_key}.{TEXT_SPAN_END_FEATURE}]')
    return 'NULL' if empty else path_key
  return (f'list_transform({path_key}, {lambda_var} -> '
          f'{_inner_select(sub_paths[1:], lambda_var, empty, span_from)})')


def _split_path_into_subpaths_of_lists(leaf_path: PathTuple) -> list[PathTuple]:
  """Split a path into a subpath of lists.

  E.g. [a, b, c, *, d, *, *] gets splits [[a, b, c], [d], [], []].
  """
  sub_paths: list[PathTuple] = []
  offset = 0
  while offset <= len(leaf_path):
    new_offset = leaf_path.index(PATH_WILDCARD,
                                 offset) if PATH_WILDCARD in leaf_path[offset:] else len(leaf_path)
    sub_path = leaf_path[offset:new_offset]
    sub_paths.append(sub_path)
    offset = new_offset + 1
  return sub_paths


def _select_sql(path: PathTuple,
                flatten: bool,
                unnest: bool,
                empty: bool = False,
                span_from: Optional[PathTuple] = None) -> str:
  """Create a select column for a path.

  Args:
    path: A path to a feature. E.g. ['a', 'b', 'c'].
    flatten: Whether to flatten the result.
    unnest: Whether to unnest the result.
    empty: Whether to return an empty list (used for embedding signals that don't need the data).
    span_from: The path this span is derived from. If specified, the span will be resolved
      to a substring of the original string.
  """
  sub_paths = _split_path_into_subpaths_of_lists(path)
  selection = _inner_select(sub_paths, None, empty, span_from)
  # We only flatten when the result of a nested list to avoid segfault.
  is_result_nested_list = len(sub_paths) >= 3  # E.g. subPaths = [[a, b, c], *, *].
  if flatten and is_result_nested_list:
    selection = f'flatten({selection})'
  # We only unnest when the result is a list. // E.g. subPaths = [[a, b, c], *].
  is_result_a_list = len(sub_paths) >= 2
  if unnest and is_result_a_list:
    selection = f'unnest({selection})'
  return selection


def read_source_manifest(dataset_path: str) -> SourceManifest:
  """Read the manifest file."""
  with open_file(os.path.join(dataset_path, MANIFEST_FILENAME), 'r') as f:
    return SourceManifest.parse_raw(f.read())


def _signal_dir(enriched_path: PathTuple) -> str:
  """Get the filename prefix for a signal parquet file."""
  path_without_wildcards = (p for p in enriched_path if p != PATH_WILDCARD)
  return os.path.join(*path_without_wildcards)


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


class SignalManifest(BaseModel):
  """The manifest that describes a signal computation including schema and parquet files."""
  # List of a parquet filepaths storing the data. The paths are relative to the manifest.
  files: list[str]

  # An identifier for this parquet table. Will be used as the view name in SQL.
  parquet_id: str

  data_schema: Schema
  signal: Signal

  # The column path that this signal is derived from.
  enriched_path: PathTuple

  # The filename of the embedding when the signal is an embedding.
  embedding_filename: Optional[str]

  @validator('signal', pre=True)
  def parse_signal(cls, signal: dict) -> Signal:
    """Parse a signal to its specific subclass instance."""
    return resolve_signal(signal)


def _merge_cells(dest_cell: ItemValue, source_cell: ItemValue) -> None:
  if source_cell is None or isinstance(source_cell, float) and math.isnan(source_cell):
    # Nothing to merge here (missing value).
    return
  if isinstance(dest_cell, dict):
    if not isinstance(source_cell, dict):
      raise ValueError(f'Failed to merge cells. Destination is a dict ({dest_cell!r}), '
                       f'but source is not ({source_cell!r}).')
    for key, value in source_cell.items():
      if key not in dest_cell:
        dest_cell[key] = value
      else:
        _merge_cells(dest_cell[key], value)
  elif isinstance(dest_cell, list):
    if not isinstance(source_cell, list):
      raise ValueError('Failed to merge cells. Destination is a list, but source is not.')
    for dest_subcell, source_subcell in zip(dest_cell, source_cell):
      _merge_cells(dest_subcell, source_subcell)
  else:
    # Primitives can be merged together if they are equal. This can happen if a user selects a
    # column that is the child of another.
    # NOTE: This can be removed if we fix https://github.com/lilacai/lilac/issues/166.
    if source_cell != dest_cell:
      raise ValueError(f'Cannot merge source "{source_cell!r}" into destination "{dest_cell!r}"')


def merge_values(destination: pd.Series, source: pd.Series) -> pd.Series:
  """Merge two series of values recursively."""
  for dest_cell, source_cell in zip(destination, source):
    _merge_cells(dest_cell, source_cell)
  return destination


def _unique_alias(column: Column) -> str:
  """Get a unique alias for a selection column."""
  if column.signal_udf:
    return make_parquet_id(column.signal_udf, column.path)
  return '.'.join(map(str, column.path))


def _col_destination_path(column: Column) -> PathTuple:
  """Get the destination path where the output of this selection column will be stored."""
  source_path = column.path

  if not column.signal_udf:
    return source_path

  signal_key = column.signal_udf.key()
  # If we are enriching a value we should store the signal data in the value's parent.
  if source_path[-1] == VALUE_KEY:
    dest_path = (*source_path[:-1], signal_key)
  else:
    dest_path = (*source_path, signal_key)

  return dest_path


def _root_column(manifest: SignalManifest) -> str:
  """Returns the root column of a signal manifest."""
  field_keys = manifest.data_schema.fields.keys()
  if len(field_keys) != 2:
    raise ValueError('Expected exactly two fields in signal manifest, '
                     f'the row UUID and root this signal is enriching. Got {field_keys}.')
  return next(filter(lambda field: field != UUID_COLUMN, manifest.data_schema.fields.keys()))


def _derived_from_path(path: PathTuple, schema: Schema) -> PathTuple:
  # Find the closest parent of `path` that is a signal root.
  for i in reversed(range(len(path))):
    sub_path = path[:i]
    if schema.get_field(sub_path).signal is not None:
      # Skip the signal name at the end to get the source path that was enriched.
      return _make_value_path(sub_path[:-1])
  raise ValueError('Cannot find the source path for the enriched path: {path}')


def _make_value_path(path: PathTuple) -> PathTuple:
  """Returns the path to the value field of the given path."""
  if path[-1] != VALUE_KEY and path[0] != UUID_COLUMN:
    return (*path, VALUE_KEY)
  return path


def _make_schema_from_path(path: PathTuple, field: Field) -> Schema:
  """Returns a schema that contains only the given path."""
  for sub_path in reversed(path):
    if sub_path == PATH_WILDCARD:
      field = Field(repeated_field=field)
    else:
      field = Field(fields={sub_path: field})
  return Schema(fields=field.fields)


def _replace_nan_with_none(df: pd.DataFrame) -> pd.DataFrame:
  """DuckDB returns np.nan for missing field in string column, replace with None for correctness."""
  # TODO(https://github.com/duckdb/duckdb/issues/4066): Remove this once duckdb fixes upstream.
  for col in df.columns:
    if is_object_dtype(df[col]):
      df[col].replace(np.nan, None, inplace=True)
  return df


def _offset_any_span(offset: int, item: ItemValue, schema: Field) -> None:
  """Offsets any spans inplace by the given parent offset."""
  if schema.dtype == DataType.STRING_SPAN:
    item = cast(dict, item)
    item[VALUE_KEY]['start'] += offset
    item[VALUE_KEY]['end'] += offset
  if schema.fields:
    item = cast(dict, item)
    for key, sub_schema in schema.fields.items():
      _offset_any_span(offset, item[key], sub_schema)
  if schema.repeated_field:
    item = cast(list, item)
    for sub_item in item:
      _offset_any_span(offset, sub_item, schema.repeated_field)


def _schema_has_spans(field: Field) -> bool:
  if field.dtype and field.dtype == DataType.STRING_SPAN:
    return True
  if field.fields:
    children_have_spans = any(_schema_has_spans(sub_field) for sub_field in field.fields.values())
    if children_have_spans:
      return True
  if field.repeated_field:
    return _schema_has_spans(field.repeated_field)
  return False
