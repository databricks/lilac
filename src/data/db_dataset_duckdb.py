"""The DuckDB implementation of the dataset database."""
import functools
import glob
import os
import re
from typing import Any, Iterable, Iterator, Optional, Sequence, Type, Union, cast

import duckdb
import numpy as np
import pandas as pd
from pandas.api.types import is_object_dtype
from pydantic import BaseModel, validator
from typing_extensions import override

from ..concepts.db_concept import DISK_CONCEPT_MODEL_DB, ConceptModelDB
from ..config import CONFIG, data_path
from ..embeddings.embedding import EmbeddingSignal
from ..embeddings.vector_store import VectorStore
from ..embeddings.vector_store_numpy import NumpyVectorStore
from ..schema import (
  ENTITY_FEATURE_KEY,
  LILAC_COLUMN,
  MANIFEST_FILENAME,
  PATH_WILDCARD,
  TEXT_SPAN_END_FEATURE,
  TEXT_SPAN_START_FEATURE,
  UUID_COLUMN,
  DataType,
  EnrichmentType,
  Field,
  Item,
  ItemValue,
  Path,
  PathTuple,
  RichData,
  Schema,
  SourceManifest,
  enrichment_supports_dtype,
  is_float,
  is_integer,
  is_ordinal,
  normalize_path,
)
from ..signals.concept_scorer import ConceptScoreSignal
from ..signals.signal import Signal
from ..signals.signal_registry import resolve_signal
from ..tasks import TaskId, progress
from ..utils import DebugTimer, get_dataset_output_dir, log, open_file
from . import db_dataset
from .dataset_utils import (
  create_signal_schema,
  flatten,
  flatten_keys,
  merge_schemas,
  path_is_from_lilac,
  read_embedding_index,
  replace_embeddings_with_none,
  schema_contains_path,
  unflatten,
  wrap_in_dicts,
  write_embeddings_to_disk,
  write_items_to_parquet,
)
from .db_dataset import (
  Bins,
  Column,
  ColumnId,
  Comparison,
  DatasetDB,
  DatasetManifest,
  Filter,
  FilterLike,
  GroupsSortBy,
  MediaResult,
  NamedBins,
  SelectGroupsResult,
  SelectRowsResult,
  SignalTransform,
  SignalUDF,
  SortOrder,
  StatsResult,
  column_from_identifier,
  make_parquet_id,
)

DEBUG = CONFIG['DEBUG'] == 'true' if 'DEBUG' in CONFIG else False
UUID_INDEX_FILENAME = 'uuids.npy'

SIGNAL_MANIFEST_SUFFIX = 'signal_manifest.json'
ENTITY_INDEX_MANIFEST_SUFFIX = 'entity_manifest.json'
SOURCE_VIEW_NAME = 'source'

# Sample size for approximating the distinct count of a column.
SAMPLE_SIZE_DISTINCT_COUNT = 100_000

COMPARISON_TO_OP: dict[Comparison, str] = {
  Comparison.EQUALS: '=',
  Comparison.NOT_EQUAL: '!=',
  Comparison.GREATER: '>',
  Comparison.GREATER_EQUAL: '>=',
  Comparison.LESS: '<',
  Comparison.LESS_EQUAL: '<=',
  Comparison.IN: 'in',
}


class DuckDBSelectGroupsResult(SelectGroupsResult):
  """The result of a select groups query backed by DuckDB."""

  def __init__(self, df: pd.DataFrame) -> None:
    """Initialize the result."""
    # DuckDB returns np.nan for missing field in string column, replace with None for correctness.
    value_column = 'value'
    # TODO(https://github.com/duckdb/duckdb/issues/4066): Remove this once duckdb fixes upstream.
    if is_object_dtype(df[value_column]):
      df[value_column].replace(np.nan, None, inplace=True)

    self._df = df

  @override
  def __iter__(self) -> Iterator:
    return (tuple(row) for _, row in self._df.iterrows())

  @override
  def df(self) -> pd.DataFrame:
    """Convert the result to a pandas DataFrame."""
    return self._df


class DatasetDuckDB(DatasetDB):
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
    self._create_view('t', self._source_manifest.files)

    # Maps a column path and embedding to the vector store. This is lazily generated as needed.
    self._col_vector_stores: dict[PathTuple, VectorStore] = {}
    self.vector_store_cls = vector_store_cls
    self._concept_model_db = concept_model_db

  def _create_view(self, view_name: str, files: list[str]) -> None:
    parquet_files = [os.path.join(self.dataset_path, filename) for filename in files]
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
    self._create_view(SOURCE_VIEW_NAME, self._source_manifest.files)

    # Add the signal column groups.
    for root, _, files in os.walk(self.dataset_path):
      for file in files:
        if not file.endswith(SIGNAL_MANIFEST_SUFFIX):
          continue

        with open_file(os.path.join(root, file)) as f:
          signal_manifest = SignalManifest.parse_raw(f.read())
        self._signal_manifests.append(signal_manifest)
        self._create_view(signal_manifest.parquet_id, signal_manifest.files)

    merged_schema = merge_schemas([self._source_manifest.data_schema] +
                                  [m.data_schema for m in self._signal_manifests])
    # The logic below generates the following example query:
    # CREATE OR REPLACE VIEW t AS (
    #   SELECT
    #     source.*,
    #     "parquet_id1"."__LILAC__" AS "parquet_id1",
    #     "parquet_id2"."__LILAC__" AS "parquet_id2"
    #   FROM source JOIN "parquet_id1" USING (uuid,) JOIN "parquet_id2" USING (uuid,)
    # );
    select_sql = ', '.join([f'{SOURCE_VIEW_NAME}.*'] + [
      f'"{manifest.parquet_id}"."{LILAC_COLUMN}" AS "{manifest.parquet_id}"'
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
    return self._recompute_joint_table(latest_mtime)

  def count(self, filters: Optional[list[FilterLike]] = None) -> int:
    """Count the number of rows."""
    raise NotImplementedError('count is not yet implemented for DuckDB.')

  def _get_vector_store(self, path: PathTuple) -> VectorStore:
    if path not in self._col_vector_stores:
      embedding_signal_manifest = next(
        m for m in self._signal_manifests if schema_contains_path(m.data_schema, path))
      if not embedding_signal_manifest:
        raise ValueError(f'No embedding found for path {path}.')
      if not embedding_signal_manifest.embedding_filename:
        raise ValueError(f'Signal manifest for path {path} is not an embedding. '
                         f'Got signal manifest: {embedding_signal_manifest}')

      embedding_index = read_embedding_index(self.dataset_path,
                                             embedding_signal_manifest.embedding_filename)
      # Get all the embeddings and pass it to the vector store.
      vector_store = self.vector_store_cls()
      vector_store.add(embedding_index.keys, embedding_index.embeddings)
      # Cache the vector store.
      self._col_vector_stores[path] = vector_store

    return self._col_vector_stores[path]

  @override
  def compute_signal_column(self,
                            signal: Signal,
                            column: ColumnId,
                            task_id: Optional[TaskId] = None) -> None:
    column = column_from_identifier(column)
    if isinstance(column.feature, Column):
      raise ValueError(f'Cannot compute a signal for {column} as it is not a leaf feature.')

    signal_col = SignalUDF(signal, column, alias='value')
    enriched_path = _col_destination_path(signal_col)
    spec = _split_path_into_subpaths_of_lists(enriched_path)

    select_rows_result = self.select_rows([signal_col], task_id=task_id, resolve_span=True)
    df = select_rows_result.df()
    values = df['value']

    source_path = normalize_path(column.feature)
    signal_key = signal.key()
    signal_out_prefix = signal_filename_prefix(source_path=source_path, signal_key=signal_key)
    signal_schema = create_signal_schema(signal, source_path, self.manifest().data_schema)
    enriched_signal_items = cast(Iterable[Item], wrap_in_dicts(values, spec))
    for uuid, item in zip(df[UUID_COLUMN], enriched_signal_items):
      item[UUID_COLUMN] = uuid

    is_embedding = isinstance(signal, EmbeddingSignal)
    embedding_filename = None
    if is_embedding:
      embedding_filename = write_embeddings_to_disk(
        keys=df[UUID_COLUMN],
        embeddings=values,
        output_dir=self.dataset_path,
        filename_prefix=signal_out_prefix,
        shard_index=0,
        num_shards=1)

      # Replace the embeddings with None so they are not serialized in the parquet file.
      enriched_signal_items = (replace_embeddings_with_none(item) for item in enriched_signal_items)

    enriched_signal_items = list(enriched_signal_items)
    parquet_filename, _ = write_items_to_parquet(
      items=enriched_signal_items,
      output_dir=self.dataset_path,
      schema=signal_schema,
      filename_prefix=signal_out_prefix,
      shard_index=0,
      num_shards=1)

    signal_manifest = SignalManifest(
      files=[parquet_filename],
      data_schema=signal_schema,
      signal=signal,
      enriched_path=source_path,
      parquet_id=make_parquet_id(signal, column.feature),
      embedding_filename=embedding_filename)
    signal_manifest_filepath = os.path.join(self.dataset_path,
                                            signal_manifest_filename(source_path, signal_key))
    with open_file(signal_manifest_filepath, 'w') as f:
      f.write(signal_manifest.json(exclude_none=True, indent=2))
    log(f'Wrote signal manifest to {signal_manifest_filepath}')

  def _validate_filters(self, filters: Sequence[Filter], col_aliases: set[str]) -> None:
    manifest = self.manifest()
    for filter in filters:
      if filter.path[0] in col_aliases:
        # This is a filter on a column alias, which is always allowed.
        continue

      current_field = Field(fields=manifest.data_schema.fields)
      for path_part in filter.path:
        if path_part == PATH_WILDCARD:
          raise ValueError(f'Unable to filter on path {filter.path}. '
                           'Filtering on a repeated field is currently not supported.')
        if current_field.fields:
          if path_part not in current_field.fields:
            raise ValueError(f'Unable to filter on path {filter.path}. '
                             f'Path part "{path_part}" not found in the dataset.')
          current_field = current_field.fields[str(path_part)]
          continue
        elif current_field.repeated_field:
          if not isinstance(path_part, int) and not path_part.isdigit():
            raise ValueError(f'Unable to filter on path {filter.path}. '
                             'Filtering must be on a specific index of a repeated field')
          current_field = current_field.repeated_field
          continue
        else:
          raise ValueError(f'Unable to filter on path {filter.path}. '
                           f'Path part "{path_part}" is not defined on a primitive value.')

  def _validate_columns(self, columns: Sequence[Column]) -> None:
    manifest = self.manifest()
    for column in columns:
      if column.transform:
        if isinstance(column.transform, SignalTransform):
          path = column.feature

          # Signal transforms must operate on a leaf field.
          leaf = manifest.data_schema.leafs.get(path)
          if not leaf or not leaf.dtype:
            raise ValueError(f'Leaf "{path}" not found in dataset. '
                             'Signal transforms must operate on a leaf field.')

          # Signal transforms must have the same dtype as the leaf field.
          signal = column.transform.signal
          enrich_type = signal.enrichment_type

          if not enrichment_supports_dtype(enrich_type, leaf.dtype):
            raise ValueError(f'Leaf "{path}" has dtype "{leaf.dtype}" which is not supported '
                             f'by "{signal.key()}" with enrichment type "{enrich_type}".')

      current_field = Field(fields=manifest.data_schema.fields)
      path = column.feature
      for path_part in path:
        if isinstance(path_part, int) or path_part.isdigit():
          raise ValueError(f'Unable to select path {path}. Selecting a specific index of '
                           'a repeated field is currently not supported.')
        if current_field.fields:
          if path_part not in current_field.fields:
            raise ValueError(f'Unable to select path {path}. '
                             f'Path part "{path_part}" not found in the dataset.')
          current_field = current_field.fields[path_part]
          continue
        elif current_field.repeated_field:
          if path_part != PATH_WILDCARD:
            raise ValueError(f'Unable to select path {path}. '
                             f'Path part "{path_part}" should be a wildcard.')
          current_field = current_field.repeated_field
        else:
          raise ValueError(f'Unable to select path {path}. '
                           f'Path part "{path_part}" is not defined on a primitive value.')

  @override
  def stats(self, leaf_path: Path) -> StatsResult:
    if not leaf_path:
      raise ValueError('leaf_path must be provided')
    path = normalize_path(leaf_path)
    manifest = self.manifest()
    leaf = manifest.data_schema.leafs.get(path)
    if not leaf or not leaf.dtype:
      raise ValueError(f'Leaf "{path}" not found in dataset')

    inner_select, _ = self._create_select([Column(path, alias='val')],
                                          flatten=True,
                                          resolve_span=True)
    # Compute approximate count by sampling the data to avoid OOM.
    sample_size = SAMPLE_SIZE_DISTINCT_COUNT
    avg_length_query = ''
    if leaf.dtype == DataType.STRING:
      avg_length_query = ', avg(length(val)) as avgTextLength'

    approx_count_query = f"""
      SELECT approx_count_distinct(val) as approxCountDistinct {avg_length_query}
      FROM (SELECT {inner_select} FROM t LIMIT {sample_size});
    """
    row = self._query(approx_count_query)[0]
    approx_count_distinct = row[0]

    total_count_query = f'SELECT count(val) FROM (SELECT {inner_select} FROM t)'
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
        FROM (SELECT {inner_select} FROM t);
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
    if not bins and stats.approx_count_distinct >= db_dataset.TOO_MANY_DISTINCT:
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
    inner_select = _make_select_column(path)
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
    if not columns:
      # Select all columns.
      columns = list(self.manifest().data_schema.fields.keys())

    cols = [column_from_identifier(column) for column in columns or []]
    # Always return the UUID column.
    col_paths = [col.feature for col in cols]
    if (UUID_COLUMN,) not in col_paths:
      cols.append(column_from_identifier(UUID_COLUMN))

    self._validate_columns(cols)
    select_query, columns_to_merge = self._create_select(
      cols, flatten=False, resolve_span=resolve_span, combine_columns=combine_columns)
    con = self.con.cursor()
    query = con.sql(f'SELECT {select_query} FROM t')

    col_aliases = set(columns_to_merge.keys())
    udf_aliases = set(col.alias or _unique_alias(col) for col in cols if col.transform)
    filters, udf_filters = self._normalize_filters(filters, col_aliases, udf_aliases)
    filter_queries = self._create_where(filters)
    if filter_queries:
      query = query.filter(' AND '.join(filter_queries))

    sort_by_paths = [normalize_path(path) for path in (sort_by or [])]
    sort_cols_after_udf: list[str] = []
    if sort_by_paths:
      for sort_by_path in sort_by_paths:
        if sort_by_path[0] not in col_aliases and sort_by_path not in col_paths:
          raise ValueError(
            f'Column {sort_by_path} is not defined as an alias in the given columns and is not '
            'defined in the select. The sort by path must be defined in either the columns or as '
            'a column alias.'
            f'Available sort by aliases: {col_aliases}.\n'
            f'Available columns: {columns}.\n')

      if not sort_order:
        raise ValueError(
          'Sort order is undefined but sort by is defined. Please define a sort_order')

      sort_cols_before_udf: list[str] = []
      for sort_by_path in sort_by_paths:
        sort_col = self._path_to_col(sort_by_path)
        # Separate sort columns into two groups: those that need to be sorted before and after UDFs.
        if str(sort_by_path[0]) in udf_aliases:
          sort_cols_after_udf.append(sort_col)
        else:
          sort_cols_before_udf.append(sort_col)

      if sort_cols_before_udf:
        query = query.order(f'{", ".join(sort_cols_before_udf)} {sort_order.value}')

    if limit and not sort_cols_after_udf:
      query = query.limit(limit, offset or 0)

    # Download the data so we can run UDFs on it in Python.
    df = query.df()

    already_sorted = False

    # Run UDFs on the transformed columns.
    udf_columns = [col for col in cols if col.transform]
    for udf_col in udf_columns:
      transform = udf_col.transform

      if isinstance(transform, SignalTransform):
        signal = transform.signal

        if isinstance(signal, ConceptScoreSignal):
          # Make sure the model is in sync.
          concept_model = self._concept_model_db.get(signal.namespace, signal.concept_name,
                                                     signal.embedding_name)
          self._concept_model_db.sync(concept_model)

        signal_column = udf_col.alias or _unique_alias(udf_col)
        input = df[signal_column]

        with DebugTimer(f'Computing signal "{signal}"'):
          if signal.enrichment_type in [EnrichmentType.TEXT_EMBEDDING]:
            # The input is an embedding.
            vector_store = self._get_vector_store(udf_col.feature)

            # If we are sorting by the topk of a signal column, we can utilize the vector store
            # via `signal.vector_compute_topk` and then use the topk to filter the dataframe. This
            # is much faster than computing the signal for all rows and then sorting.
            if self._sorting_by_topk_of_signal(limit, sort_order, sort_cols_after_udf,
                                               signal_column):
              already_sorted = True
              k = (limit or 0) + (offset or 0)
              topk = signal.vector_compute_topk(k, vector_store)
              unique_uuids = list(dict.fromkeys([key[0] for key, _ in topk]))
              df.set_index(UUID_COLUMN, drop=False, inplace=True)
              # Filter the dataframe by uuids that have at least one entity in top k.
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
              df[signal_column] = unflatten(signal_out, input)
          else:
            flat_input = cast(list[RichData], flatten(input))
            signal_out = signal.compute(flat_input)
            # Add progress.
            if task_id is not None:
              signal_out = progress(signal_out, task_id=task_id, estimated_len=len(flat_input))
            signal_out = list(signal_out)

            if len(signal_out) != len(flat_input):
              raise ValueError(
                f'The signal generated {len(signal_out)} values but the input data had '
                f"{len(flat_input)} values. This means the signal either didn't generate a "
                '"None" for a sparse output, or generated too many items.')
            df[signal_column] = unflatten(signal_out, input)
      else:
        raise ValueError(f'Unsupported transform: {transform}')

    if udf_filters or sort_cols_after_udf:
      # Re-upload the udf outputs to duckdb so we can filter/sort on them.
      query = con.from_df(df)

      if udf_filters:
        udf_filter_queries = self._create_where(udf_filters)
        if udf_filter_queries:
          query = query.filter(' AND '.join(udf_filter_queries))

      if not already_sorted and sort_cols_after_udf:
        if not sort_order:
          raise ValueError(
            'Sort order is undefined but sort by is defined. Please define a sort_order')
        query = query.order(f'{", ".join(sort_cols_after_udf)} {sort_order.value}')

      if limit:
        query = query.limit(limit, offset or 0)

      df = query.df()

    for final_col_name, temp_columns in columns_to_merge.items():
      for temp_col_name, column in temp_columns:
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

    query.close()
    con.close()

    if combine_columns:
      # Since we aliased every column to `*`, the object with have only '*' as the key. We need to
      # elevate the all the columns under '*'.
      df = pd.DataFrame.from_records(df['*'])

    # DuckDB returns np.nan for missing field in string column, replace with None for correctness.
    for col in df.columns:
      if is_object_dtype(df[col]):
        df[col].replace(np.nan, None, inplace=True)

    return SelectRowsResult(df)

  @override
  def media(self, item_id: str, leaf_path: Path) -> MediaResult:
    raise NotImplementedError('Media is not yet supported for the DuckDB implementation.')

  def _create_select_column(self, column: Column, manifest: DatasetManifest, flatten: bool,
                            resolve_span: bool) -> tuple[str, list[str]]:
    leafs = manifest.data_schema.leafs
    path = column.feature
    is_span = (path in leafs and leafs[path].dtype == DataType.STRING_SPAN)
    span_field = leafs[path] if resolve_span and is_span else None
    # We doing a vector-based computation, we do not need to select the actual data, just the uuids
    # plus an arbitrarily nested array of `None`s`.
    empty = bool(
      column.transform and isinstance(column.transform, SignalTransform) and
      manifest.data_schema.get_field(path).dtype == DataType.EMBEDDING)
    select_queries: list[str] = []
    temp_column_names: list[str] = []

    parquet_manifests: list[Union[SourceManifest, SignalManifest]] = [
      self._source_manifest, *self._signal_manifests
    ]

    for m in parquet_manifests:
      if not schema_contains_path(m.data_schema, path):
        # Skip this parquet file if it doesn't contain the path.
        continue

      if isinstance(m, SignalManifest) and path == (UUID_COLUMN,):
        # Do not select UUID from the signal because it's already in the source.
        continue

      temp_column_name = column.alias or _unique_alias(column)
      if path_is_from_lilac(path):
        m = cast(SignalManifest, m)
        select_path = (m.parquet_id, *path[1:])
        if path not in leafs:
          # Non-leafs can have data in multiple manifests so we need to namespace.
          temp_column_name = f'{temp_column_name}/{m.parquet_id}'
      else:
        select_path = path
      temp_column_names.append(temp_column_name)
      col = _make_select_column(select_path, flatten=flatten, empty=empty, span_field=span_field)
      select_queries.append(f'{col} AS "{temp_column_name}"')

    return ', '.join(select_queries), temp_column_names

  def _create_select(self,
                     columns: list[Column],
                     flatten: bool,
                     resolve_span: bool,
                     combine_columns: bool = False
                    ) -> tuple[str, dict[str, list[tuple[str, Column]]]]:
    """Create the select statement."""
    manifest = self.manifest()
    # Map a final column name to a list of temporary namespaced column names that need to be merged.
    alias_to_temp_col_names: dict[str, list[tuple[str, Column]]] = {}
    select_queries: list[str] = []

    for column in columns:
      select_str, temp_column_names = self._create_select_column(column, manifest, flatten,
                                                                 resolve_span)
      # If `combine_columns` is True, we alias every column to `*` so that we can merge them all.
      alias = '*' if combine_columns else (column.alias or _unique_alias(column))
      if alias not in alias_to_temp_col_names:
        alias_to_temp_col_names[alias] = []
      alias_to_temp_col_names[alias].extend([(x, column) for x in temp_column_names])

      select_queries.append(select_str)
    return ', '.join(select_queries), alias_to_temp_col_names

  def _normalize_filters(self, filter_likes: Optional[Sequence[FilterLike]], col_aliases: set[str],
                         udf_aliases: set[str]) -> tuple[list[Filter], list[Filter]]:
    """Normalize `FilterLike` to `Filter` and split into filters on source and filters on UDFs."""
    filter_likes = filter_likes or []
    filters: list[Filter] = []
    udf_filters: list[Filter] = []

    for filter in filter_likes:
      # Normalize `FilterLike` to `Filter`.
      if not isinstance(filter, Filter):
        path_tuple = filter[0]
        if isinstance(path_tuple, str):
          path_tuple = (path_tuple,)
        elif isinstance(path_tuple, Column):
          path_tuple = path_tuple.feature
        filter = Filter(path=path_tuple, comparison=filter[1], value=filter[2])
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
    for filter in filters:
      col_name = self._path_to_col(filter.path)
      op = COMPARISON_TO_OP[filter.comparison]
      filter_val = filter.value
      if isinstance(filter_val, list):
        if op != 'in':
          raise ValueError('filter with array value can only use the IN comparison')
        wrapped_filter_val = [f"'{part}'" for part in filter_val]
        filter_val = f'({", ".join(wrapped_filter_val)})'
      elif isinstance(filter_val, str):
        filter_val = f"'{filter_val}'"
      elif isinstance(filter_val, bytes):
        filter_val = _bytes_to_blob_literal(filter_val)
      else:
        filter_val = str(filter_val)
      filter_query = f'{col_name} {op} {filter_val}'
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
    df = result.df()
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
                  span_field: Optional[Field] = None) -> str:
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
    if span_field:
      if not span_field.derived_from:
        raise ValueError('derived_from from must be specified for span.')
      derived_col = _make_select_column(span_field.derived_from)
      path_key = (f'{derived_col}[{path_key}.{TEXT_SPAN_START_FEATURE}+1:'
                  f'{path_key}.{TEXT_SPAN_END_FEATURE}]')
    return 'NULL' if empty else path_key
  return (f'list_transform({path_key}, {lambda_var} -> '
          f'{_inner_select(sub_paths[1:], lambda_var, empty, span_field)})')


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


def _make_select_column(leaf_path: Path,
                        flatten: bool = True,
                        empty: bool = False,
                        span_field: Optional[Field] = None) -> str:
  """Create a select column for a leaf path.

  Args:
    leaf_path: A path to a leaf feature. E.g. ['a', 'b', 'c'].
    flatten: Whether to flatten the result.
    empty: Whether to return an empty list (used for embedding signals that don't need the data).
    span_field: The field that the span is derived from. If specified, the span will be resolved
      to a substring of the original string.
  """
  path = normalize_path(leaf_path)
  sub_paths = _split_path_into_subpaths_of_lists(path)
  selection = _inner_select(sub_paths, None, empty, span_field)
  # We only flatten when the result of a nested list to avoid segfault.
  is_result_nested_list = len(sub_paths) >= 3  # E.g. subPaths = [[a, b, c], *, *].
  if flatten and is_result_nested_list:
    selection = f'flatten({selection})'
  # We only unnest when the result is a list. // E.g. subPaths = [[a, b, c], *].
  is_result_a_list = len(sub_paths) >= 2
  if flatten and is_result_a_list:
    selection = f'unnest({selection})'
  return selection


def read_source_manifest(dataset_path: str) -> SourceManifest:
  """Read the manifest file."""
  with open_file(os.path.join(dataset_path, MANIFEST_FILENAME), 'r') as f:
    return SourceManifest.parse_raw(f.read())


def signal_filename_prefix(source_path: PathTuple, signal_key: str) -> str:
  """Get the filename prefix for a signal parquet file."""
  return f"{'.'.join(map(str, source_path))}.{signal_key}"


def signal_manifest_filename(source_path: PathTuple, signal_key: str) -> str:
  """Get the filename for a signal output."""
  return f'{signal_filename_prefix(source_path, signal_key)}.{SIGNAL_MANIFEST_SUFFIX}'


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
  if isinstance(dest_cell, dict):
    if not isinstance(source_cell, dict):
      raise ValueError('Failed to merge cells. Destination is a dict, but source is not.')
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
    raise ValueError(f'Cannot merge source "{source_cell!r}" into destination "{dest_cell!r}"')


def merge_values(destination: pd.Series, source: pd.Series) -> pd.Series:
  """Merge two series of values recursively."""
  for dest_cell, source_cell in zip(destination, source):
    _merge_cells(dest_cell, source_cell)
  return destination


def _unique_alias(column: Column) -> str:
  """Get a unique alias for a selection column."""
  if column.transform and isinstance(column.transform, SignalTransform):
    return make_parquet_id(column.transform.signal, column.feature)
  return '.'.join(map(str, column.feature))


def _col_destination_path(column: Column) -> PathTuple:
  """Get the destination path where the output of this selection column will be stored."""
  source_path = column.feature

  if not column.transform:
    return source_path

  if not isinstance(column.transform, SignalTransform):
    raise ValueError(f'Cannot get destination path for transform {column.transform!r}')

  signal_key = column.transform.signal.key()
  # If we are enriching an entity we should store the signal data in the entity field's parent.
  if source_path[-1] == ENTITY_FEATURE_KEY:
    dest_path = (LILAC_COLUMN, *source_path[:-1], signal_key)
  else:
    dest_path = (LILAC_COLUMN, *source_path, signal_key)

  # If a signal is enriching output of a signal, skip the lilac prefix to avoid double prefixing.
  if path_is_from_lilac(source_path):
    dest_path = dest_path[1:]

  return dest_path
