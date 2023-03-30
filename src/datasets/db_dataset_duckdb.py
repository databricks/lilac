"""The DuckDB implementation of the dataset database."""
import functools
import itertools
import os
from typing import Iterable, Optional, Sequence, Union, cast

import duckdb
import pandas as pd
from pydantic import BaseModel, validator
from typing_extensions import override

from ..constants import data_path
from ..embeddings.embedding_index import EmbeddingIndexer
from ..embeddings.embedding_index_disk import EmbeddingIndexerDisk
from ..embeddings.embedding_registry import EmbeddingId
from ..schema import (
    MANIFEST_FILENAME,
    PATH_WILDCARD,
    TEXT_SPAN_FEATURE_NAME,
    UUID_COLUMN,
    Field,
    Path,
    PathTuple,
    Schema,
    SourceManifest,
    is_repeated_path_part,
    normalize_path,
)
from ..signals.signal import Signal
from ..signals.signal_registry import resolve_signal
from ..signals.splitters.splitter import (
    TEXT_SPAN_END_FEATURE,
    TEXT_SPAN_START_FEATURE,
)
from ..utils import (
    DebugTimer,
    get_dataset_output_dir,
    log,
    open_file,
    write_items_to_parquet,
)
from .dataset_utils import (
    create_enriched_schema,
    default_top_level_signal_col_name,
    make_enriched_items,
)
from .db_dataset import (
    Column,
    ColumnId,
    DatasetDB,
    DatasetManifest,
    Filter,
    GroupsSortBy,
    SelectRowsResult,
    SortOrder,
    column_from_identifier,
)

DEBUG = os.environ['DEBUG'] == 'true' if 'DEBUG' in os.environ else False
UUID_INDEX_FILENAME = 'uuids.npy'

SIGNAL_MANIFEST_SUFFIX = 'signal_manifest.json'
SPLIT_MANIFEST_SUFFIX = 'split_manifest.json'
SOURCE_VIEW_NAME = 'source'


class ComputedColumn(BaseModel):
  """A column that is computed/derived from another column."""

  # The parquet files that contain the column values.
  files: list[str]

  # The name of the column when merged into a larger table.
  top_level_column_name: str

  # The name of the field that contains the values.
  value_field_name: str

  # The field schema of column value.
  value_field_schema: Field

  # The path to the column this column is derived from.
  enriched_path: Path


class SelectLeafsResult(BaseModel):
  """The result of a select leafs query."""

  class Config:
    arbitrary_types_allowed = True

  duckdb_result: duckdb.DuckDBPyRelation
  repeated_idxs_col: Optional[str]
  value_column: Optional[str]


class DuckDBTableInfo(BaseModel):
  """Internal representation of a DuckDB table."""
  manifest: DatasetManifest
  computed_columns: list[ComputedColumn]


class DatasetDuckDB(DatasetDB):
  """The DuckDB implementation of the dataset database."""

  def __init__(self,
               namespace: str,
               dataset_name: str,
               embedding_indexer: Optional[EmbeddingIndexer] = None):
    super().__init__(namespace, dataset_name)

    self.dataset_path = get_dataset_output_dir(data_path(), namespace, dataset_name)

    # TODO: Infer the manifest from the parquet files so this is lighter weight.
    self._source_manifest = read_source_manifest(self.dataset_path)

    self.con = duckdb.connect(database=':memory:')
    self._create_view('t', self._source_manifest.files)

    if not embedding_indexer:
      self._embedding_indexer: EmbeddingIndexer = EmbeddingIndexerDisk(self.dataset_path)
    else:
      self._embedding_indexer = embedding_indexer

  def _create_view(self, view_name: str, files: list[str]) -> None:
    parquet_files = [os.path.join(self.dataset_path, filename) for filename in files]
    self.con.execute(f"""
      CREATE OR REPLACE VIEW "{view_name}" AS (SELECT * FROM read_parquet({parquet_files}));
    """)

  def _column_signal_manifest_files(self) -> tuple[str, ...]:
    """Return the signal manifests for all enriched columns."""
    signal_manifest_filepaths: list[str] = []
    for root, _, files in os.walk(self.dataset_path):
      for file in files:
        if file.endswith(SIGNAL_MANIFEST_SUFFIX):
          signal_manifest_filepaths.append(os.path.join(root, file))

    return tuple(signal_manifest_filepaths)

  @functools.cache
  # NOTE: This is cached, but when the list of filepaths changed the results are invalidated.
  def _recompute_joint_table(self, signal_manifest_filepaths: list[str]) -> DuckDBTableInfo:
    computed_columns: list[ComputedColumn] = []

    # Add the signal column groups.
    for signal_manifest_filepath in signal_manifest_filepaths:
      with open_file(signal_manifest_filepath) as f:
        signal_manifest = SignalManifest.parse_raw(f.read())
      value_field_name = cast(str, signal_manifest.enriched_path[0])
      signal_column = ComputedColumn(
          files=signal_manifest.files,
          top_level_column_name=signal_manifest.top_level_column_name,
          value_field_name=value_field_name,
          value_field_schema=signal_manifest.data_schema.fields[value_field_name],
          enriched_path=signal_manifest.enriched_path)
      computed_columns.append(signal_column)

    # Merge the source manifest with the computed columns.
    merged_schema = Schema(
        fields={
            **self._source_manifest.data_schema.fields,
            **{col.top_level_column_name: col.value_field_schema for col in computed_columns}
        })

    manifest = DatasetManifest(namespace=self.namespace,
                               dataset_name=self.dataset_name,
                               data_schema=merged_schema)

    # Make a joined view of all the column groups.
    self._create_view(SOURCE_VIEW_NAME, self._source_manifest.files)
    for column in computed_columns:
      self._create_view(column.top_level_column_name, column.files)

    # The logic below generates the following example query:
    # CREATE OR REPLACE VIEW t AS (
    #   SELECT
    #     source.*,
    #     "enriched.signal1"."enriched" AS "enriched.signal1",
    #     "enriched.signal2"."enriched" AS "enriched.signal2"
    #   FROM source JOIN "enriched.signal1" USING (uuid,) JOIN "enriched.signal2" USING (uuid,)
    # );
    select_sql = ', '.join([f'{SOURCE_VIEW_NAME}.*'] + [
        f'"{col.top_level_column_name}"."{col.value_field_name}" AS "{col.top_level_column_name}"'
        for col in computed_columns
    ])
    join_sql = ' '.join(
        [SOURCE_VIEW_NAME] +
        [f'join "{col.top_level_column_name}" using ({UUID_COLUMN},)' for col in computed_columns])

    sql_cmd = f"""CREATE OR REPLACE VIEW t AS (SELECT {select_sql} FROM {join_sql})"""
    self.con.execute(sql_cmd)

    return DuckDBTableInfo(manifest=manifest, computed_columns=computed_columns)

  def _table_info(self) -> DuckDBTableInfo:
    return self._recompute_joint_table(self._column_signal_manifest_files())

  @override
  def manifest(self) -> DatasetManifest:
    return self._table_info().manifest

  @functools.cache
  def columns(self) -> list[Column]:
    """Get the columns."""
    columns: list[Column] = []
    for path in self._source_manifest.data_schema.leafs.keys():
      columns.append(Column(feature=path))
    return columns

  def count(self, filters: Optional[list[Filter]] = None) -> int:
    """Count the number of rows."""
    raise NotImplementedError

  @override
  def compute_embedding_index(self, embedding: EmbeddingId, column: ColumnId) -> None:
    col = column_from_identifier(column)
    if isinstance(col.feature, Column):
      raise ValueError(f'Cannot compute a signal for {col} as it is not a leaf feature.')

    with DebugTimer(f'"_select_leafs" over "{col.feature}"'):
      select_leafs_result = self._select_leafs(path=normalize_path(col.feature))
      leafs_df = select_leafs_result.duckdb_result.to_df()

    keys = _get_keys_from_leafs(leafs_df=leafs_df, select_leafs_result=select_leafs_result)
    leaf_values = leafs_df[select_leafs_result.value_column]

    self._embedding_indexer.compute_embedding_index(column=col.feature,
                                                    embedding=embedding,
                                                    keys=keys,
                                                    data=leaf_values)

  @override
  def compute_signal_columns(self,
                             signal: Signal,
                             column: ColumnId,
                             signal_column_name: Optional[str] = None) -> str:
    column = column_from_identifier(column)
    if not signal_column_name:
      signal_column_name = default_top_level_signal_col_name(signal, column)

    signal_field = signal.fields()

    if isinstance(column.feature, Column):
      raise ValueError(f'Cannot compute a signal for {column} as it is not a leaf feature.')

    source_path = normalize_path(column.feature)
    signal_schema = create_enriched_schema(source_schema=self.manifest().data_schema,
                                           enrich_path=source_path,
                                           enrich_field=signal_field)

    if signal.embedding_based:
      # For embedding based signals, get the leaf keys and indices, creating a combined key for the
      # key + index to pass to the signal.
      with DebugTimer(f'"_select_leafs" over "{source_path}"'):
        select_leafs_result = self._select_leafs(path=source_path, only_keys=True)
        leafs_df = select_leafs_result.duckdb_result.to_df()

      keys = _get_keys_from_leafs(leafs_df=leafs_df, select_leafs_result=select_leafs_result)

      with DebugTimer(f'"compute" for embedding signal "{signal.name}" over "{source_path}"'):
        signal_outputs = signal.compute(
            keys=keys,
            get_embedding_index=(
                lambda embedding, keys: self._embedding_indexer.get_embedding_index(
                    column=source_path, embedding=embedding, keys=keys)))
    else:
      # For non-embedding bsaed signals, get the leaf values and indices.
      with DebugTimer(f'"_select_leafs" over "{source_path}"'):
        select_leafs_result = self._select_leafs(path=source_path)
        leafs_df = select_leafs_result.duckdb_result.to_df()

      with DebugTimer(f'"compute" for signal "{signal.name}" over "{source_path}"'):
        signal_outputs = signal.compute(data=leafs_df[select_leafs_result.value_column])

    # Use the repeated indices to generate the correct signal output structure.
    if select_leafs_result.repeated_idxs_col:
      repeated_idxs = leafs_df[select_leafs_result.repeated_idxs_col]

    # Repeat "None" if there are no repeated indices without allocating an array. This happens
    # when the object is a simple structure.
    repeated_idxs_iter: Iterable[Optional[list[int]]] = (
        itertools.repeat(None) if not select_leafs_result.repeated_idxs_col else repeated_idxs)

    enriched_signal_items = make_enriched_items(source_path=source_path,
                                                row_ids=leafs_df[UUID_COLUMN],
                                                leaf_items=signal_outputs,
                                                repeated_idxs=repeated_idxs_iter)

    signal_out_prefix = signal_parquet_prefix(column_name=column.alias, signal_name=signal.name)
    parquet_filename, _ = write_items_to_parquet(items=enriched_signal_items,
                                                 output_dir=self.dataset_path,
                                                 schema=signal_schema,
                                                 filename_prefix=signal_out_prefix,
                                                 shard_index=0,
                                                 num_shards=1)

    signal_manifest = SignalManifest(files=[parquet_filename],
                                     data_schema=signal_schema,
                                     signal=signal,
                                     enriched_path=source_path,
                                     top_level_column_name=signal_column_name)
    signal_manifest_filepath = os.path.join(
        self.dataset_path,
        signal_manifest_filename(column_name=column.alias, signal_name=signal.name))
    with open_file(signal_manifest_filepath, 'w') as f:
      f.write(signal_manifest.json())
    log(f'Wrote signal manifest to {signal_manifest_filepath}')

    return signal_column_name

  def _select_leafs(self, path: PathTuple, only_keys: Optional[bool] = False) -> SelectLeafsResult:
    schema_leafs = self.manifest().data_schema.leafs
    if path not in schema_leafs:
      raise ValueError(f'Path "{path}" not found in schema leafs: {schema_leafs}')

    select_span = path[-1] == TEXT_SPAN_FEATURE_NAME

    if not select_span:
      for path_component in path[0:-1]:
        if is_repeated_path_part(path_component):
          raise ValueError(
              f'Outer repeated leafs are not yet supported in _select_leafs. Requested Path: {path}'
          )
    else:
      # When we have spans, make sure there are not two repeated parts anywhere.
      num_repeated_parts = 0
      for path_component in path:
        if is_repeated_path_part(path_component):
          num_repeated_parts += 1
      if num_repeated_parts > 1:
        raise ValueError(
            'Multiple repeated leafs for spans are not yet supported in _select_leafs. '
            f'Requested Path: {path}')

    repeated_indices_col: Optional[str] = None
    is_repeated = any([is_repeated_path_part(path_part) for path_part in path])
    if is_repeated:
      inner_repeated_col = self._path_to_col(path[0:path.index(PATH_WILDCARD)],
                                             quote_each_part=True)

    data_col = 'leaf_data'
    if select_span:
      span = make_select_column(path)
      top_level_column_name = path[0]
      for computed_column in self._table_info().computed_columns:
        if computed_column.top_level_column_name == top_level_column_name:
          source_path = computed_column.enriched_path
          break

      source_path_select = make_select_column(source_path)

      # In the sub-select, return both the original text and the span.
      span_name = 'span'
      data_select = f"""
            {span} as {span_name},
            {source_path_select} as {data_col},
      """
      # In the outer select, return the sliced text. DuckDB 1-indexes array slices, and is inclusive
      # to the last index, so we only add one to the start.
      value_column = f"""{data_col}[
        {span_name}.{TEXT_SPAN_START_FEATURE} + 1:{span_name}.{TEXT_SPAN_END_FEATURE}
      ]
      """
    else:
      data_select_column = make_select_column(path)
      data_select = f"""
          {data_select_column} as {data_col},
      """
      value_column = data_col

    value_column_alias = 'value'
    repeated_indices_col = None
    if is_repeated:
      # Currently we only allow inner repeated leafs, so we can use a simple UNNEST(RANGE(...)) to
      # get the indices. When this is generalized, the RANGE has to be updated to return the list of
      # indices.
      repeated_indices_col = 'repeated_indices'
      from_table = f"""
        (
          SELECT
            {data_select if not only_keys else ''}
            UNNEST(RANGE(ARRAY_LENGTH({inner_repeated_col}))) as {repeated_indices_col},
            {UUID_COLUMN}
          FROM t
        )
      """
      leaf_select = f'{value_column} as {value_column_alias}'
    else:
      value_column = self._path_to_col(path, quote_each_part=True)
      leaf_select = f'{value_column} as {value_column_alias}'
      from_table = 't'

    query = f"""
    SELECT
      {UUID_COLUMN},
      {f'{repeated_indices_col},' if repeated_indices_col else ''}
      {leaf_select if not only_keys else ''}
    FROM {from_table}
    """
    return SelectLeafsResult(duckdb_result=self._query(query),
                             value_column=value_column_alias,
                             repeated_idxs_col=repeated_indices_col)

  def _validate_columns(self, columns: Sequence[Column]) -> None:
    manifest = self.manifest()
    for column in columns:
      current_field = Field(fields=manifest.data_schema.fields)
      path = cast(Path, column.feature)
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
  def select_groups(self,
                    columns: Optional[Sequence[ColumnId]] = None,
                    filters: Optional[Sequence[Filter]] = None,
                    sort_by: Optional[GroupsSortBy] = None,
                    sort_order: Optional[SortOrder] = SortOrder.DESC,
                    limit: Optional[int] = 100) -> pd.DataFrame:
    raise NotImplementedError

  @override
  def select_rows(self,
                  columns: Optional[Sequence[ColumnId]] = None,
                  filters: Optional[Sequence[Filter]] = None,
                  sort_by: Optional[Sequence[str]] = None,
                  sort_order: Optional[SortOrder] = SortOrder.DESC,
                  limit: Optional[int] = 100) -> SelectRowsResult:
    cols = [column_from_identifier(column) for column in columns or []]
    self._validate_columns(cols)

    select_query, col_aliases = self._create_select(cols)
    where_query = self._create_where(filters)

    # Sort.
    sort_query = ''
    if sort_by:
      sort_by_query_parts = []
      for sort_by_alias in sort_by:
        if sort_by_alias not in col_aliases:
          raise ValueError(
              f'Column {sort_by_alias} is not defined as an alias in the given columns. '
              f'Available sort by aliases: {col_aliases}')
        sort_by_query_parts.append(sort_by_alias)

      if not sort_order:
        raise ValueError(
            'Sort order is undefined but sort by is defined. Please define a sort_order')
      sort_order_query = sort_order.value

      sort_by_query = ', '.join(sort_by_query_parts)
      sort_query = f'ORDER BY {sort_by_query} {sort_order_query}'

    limit_query = f'LIMIT {limit}' if limit else ''

    query = f"""
      SELECT {select_query}
      FROM t
      {where_query}
      {sort_query}
      {limit_query}
    """

    query_results = cast(list, self._query(query).fetchall())

    item_rows = map(lambda row: dict(zip(col_aliases, row)), query_results)
    return SelectRowsResult(item_rows)

  def _create_select(
      self,
      columns: Optional[list[Column]] = None,
  ) -> tuple[str, list[str]]:
    """Create the select statement."""
    if not columns:
      columns = self.columns()
    # Always return the UUID column.
    columns += [Column(UUID_COLUMN)]

    select_queries: list[str] = []
    aliases: list[str] = []

    for column in columns:
      if isinstance(column.feature, Column):
        raise ValueError('Transforms are not yet supported.')
      aliases.append(column.alias)
      select_queries.append(f'{self._path_to_col(column.feature)} AS "{column.alias}"')

    return ', '.join(select_queries), aliases

  def _create_where(self, filters: Optional[Sequence[Filter]] = None) -> str:
    if not filters:
      return ''
    raise ValueError('Filters are not yet supported for the DuckDB implementation.')

  def _query(self, query: str) -> duckdb.DuckDBPyRelation:
    """Execute a query that returns a dataframe."""
    if not DEBUG:
      return self.con.query(query)

    # Debug mode.
    log('Executing:')
    log(query)
    with DebugTimer('Query'):
      result = self.con.query(query)

    return result

  def _path_to_col(self, path: Path, quote_each_part: bool = True) -> str:
    """Convert a path to a column name."""
    if isinstance(path, str):
      path = (path,)
    return '.'.join([f'"{path_comp}"' if quote_each_part else str(path_comp) for path_comp in path])


def _inner_select(sub_paths: list[list[str]], inner_var: Optional[str] = None) -> str:
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
    return path_key
  return f'list_transform({path_key}, {lambda_var} -> {_inner_select(sub_paths[1:], lambda_var)})'


def _split_path_into_subpaths_of_lists(leaf_path: list[str]) -> list[list[str]]:
  """Split a path into a subpath of lists.

  E.g. [a, b, c, *, d, *, *] gets splits [[a, b, c], [d], [], []].
  """
  sub_paths: list[list[str]] = []
  offset = 0
  while offset <= len(leaf_path):
    new_offset = leaf_path.index(PATH_WILDCARD,
                                 offset) if PATH_WILDCARD in leaf_path[offset:] else len(leaf_path)
    sub_path = leaf_path[offset:new_offset]
    sub_paths.append(sub_path)
    offset = new_offset + 1
  return sub_paths


def make_select_column(leaf_path: Path) -> str:
  """Create a select column for a leaf path."""
  path = cast(list, normalize_path(leaf_path))
  sub_paths = _split_path_into_subpaths_of_lists(path)
  selection = _inner_select(sub_paths, None)
  # We only flatten when the result of a nested list to avoid segfault.
  is_result_nested_list = len(sub_paths) >= 3  # E.g. subPaths = [[a, b, c], *, *].
  if is_result_nested_list:
    selection = f'flatten({selection})'
  # We only unnest when the result is a list. // E.g. subPaths = [[a, b, c], *].
  is_result_a_list = len(sub_paths) >= 2
  if is_result_a_list:
    selection = f'unnest({selection})'
  return selection


def _get_repeated_key(row_id: Union[bytes, bytearray], repeated_idxs: list[int]) -> bytes:
  return bytes(row_id) + b'_' + bytes(repeated_idxs)


def _get_keys_from_leafs(leafs_df: pd.DataFrame,
                         select_leafs_result: SelectLeafsResult) -> Iterable[bytes]:
  """Compute the keys from the dataframe and select leafs result, adding indices to keys."""
  # Add the repeated indices to the create a repeated key so we can store different values for the
  # same row uuid.
  if select_leafs_result.repeated_idxs_col:
    # Add the repeated indices to the create a repeated key so we can store different values for the
    # same row uuid.
    return leafs_df.apply(lambda row: _get_repeated_key(row[
        UUID_COLUMN], [row[select_leafs_result.repeated_idxs_col]]),
                          axis=1)
  else:
    # Cast from bytearray => bytes.
    return leafs_df[UUID_COLUMN].apply(lambda row_id: bytes(row_id))


def read_source_manifest(dataset_path: str) -> SourceManifest:
  """Read the manifest file."""
  with open_file(os.path.join(dataset_path, MANIFEST_FILENAME), 'r') as f:
    return SourceManifest.parse_raw(f.read())


def signal_parquet_prefix(column_name: str, signal_name: str) -> str:
  """Get the filename prefix for a signal parquet file."""
  return f'{column_name}.{signal_name}'


def signal_manifest_filename(column_name: str, signal_name: str) -> str:
  """Get the filename for a signal output."""
  return f'{column_name}.{signal_name}.{SIGNAL_MANIFEST_SUFFIX}'


def split_column_name(column: str, split_name: str) -> str:
  """Get the name of a split column."""
  return f'{column}.{split_name}'


def split_parquet_prefix(column_name: str, splitter_name: str) -> str:
  """Get the filename prefix for a split parquet file."""
  return f'{column_name}.{splitter_name}'


def split_manifest_filename(column_name: str, splitter_name: str) -> str:
  """Get the filename for a split output."""
  return f'{column_name}.{splitter_name}.{SPLIT_MANIFEST_SUFFIX}'


class SignalManifest(BaseModel):
  """The manifest that describes a signal computation including schema and parquet files."""
  # List of a parquet filepaths storing the data. The paths are relative to the manifest.
  files: list[str]

  # The column name that this signal is stored in. This provides the top-level path to the computed
  # signal values.
  top_level_column_name: str

  data_schema: Schema
  signal: Signal

  # The column path that this signal is derived from.
  enriched_path: Path

  @validator('signal', pre=True)
  def parse_signal(cls, signal: dict) -> Signal:
    """Parse a signal to its specific subclass instance."""
    return resolve_signal(signal)
