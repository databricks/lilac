"""The DuckDB implementation of the dataset database."""
import functools
import itertools
import os
from typing import Iterable, Optional, Sequence, cast

import duckdb
import pandas as pd
from pydantic import BaseModel, validator
from typing_extensions import override  # type: ignore

from ..constants import data_path
from ..embeddings.embedding_index import EmbeddingIndexer
from ..embeddings.embedding_index_disk import EmbeddingIndexerDisk
from ..embeddings.embedding_registry import EmbeddingId
from ..schema import (
    MANIFEST_FILENAME,
    UUID_COLUMN,
    Item,
    Path,
    Schema,
    SourceManifest,
    is_repeated_path_part,
    normalize_path,
)
from ..signals.signal import Signal
from ..signals.signal_registry import resolve_signal
from ..splitters.splitter_registry import resolve_splitter
from ..splitters.text_splitter import SPLITS_FIELDS, TextSplitter, item_from_spans
from ..utils import (
    DebugTimer,
    get_dataset_output_dir,
    log,
    open_file,
    write_items_to_parquet,
)
from .dataset_utils import create_enriched_schema, make_enriched_items
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


class ColumnGroup(BaseModel):
  """A group of columns stored in a parquet file."""

  files: list[str]

  # The signal name that created this group.
  signal_name: Optional[str]
  # The split name that created this group.
  splitter_name: Optional[str]
  # The column path that this group is derived from.
  original_column_path: Optional[Path]

  # The schema of this column group.
  data_schema: Schema


class SelectLeafsResult(BaseModel):
  """The result of a select leafs query."""

  class Config:
    arbitrary_types_allowed = True

  duckdb_result: duckdb.DuckDBPyRelation
  repeated_idxs_col: Optional[str]


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
      CREATE OR REPLACE VIEW {view_name} AS (SELECT * FROM read_parquet({parquet_files}));
    """)

  def _column_signal_manifest_files(self) -> tuple[str, ...]:
    """Return the signal manifests for all enriched columns."""
    signal_manifest_filepaths: list[str] = []
    for root, _, files in os.walk(self.dataset_path):
      for file in files:
        if file.endswith(SIGNAL_MANIFEST_SUFFIX):
          signal_manifest_filepaths.append(os.path.join(root, file))

    return tuple(signal_manifest_filepaths)

  def _column_split_manifest_files(self) -> tuple[str, ...]:
    """Return the signal manifests for all enriched columns."""
    split_manifest_filepaths: list[str] = []
    for root, _, files in os.walk(self.dataset_path):
      for file in files:
        if file.endswith(SPLIT_MANIFEST_SUFFIX):
          split_manifest_filepaths.append(os.path.join(root, file))

    return tuple(split_manifest_filepaths)

  @functools.cache
  # NOTE: This is cached, but when the list of filepaths changed the results are invalidated.
  def _column_groups(self, signal_manifest_filepaths: list[str],
                     split_manifest_filepaths: list[str]) -> list[ColumnGroup]:
    column_groups: list[ColumnGroup] = []
    # Add the source column group.
    column_groups.append(
        ColumnGroup(files=self._source_manifest.files,
                    signal_name=None,
                    original_column_path=None,
                    data_schema=self._source_manifest.data_schema))

    # Add the signal column groups.
    for signal_manifest_filepath in signal_manifest_filepaths:
      with open_file(signal_manifest_filepath) as f:
        signal_manifest = SignalManifest.parse_raw(f.read())

      column_groups.append(
          ColumnGroup(files=signal_manifest.files,
                      signal_name=signal_manifest.signal.signal_name,
                      original_column_path=signal_manifest.enriched_path,
                      data_schema=signal_manifest.data_schema))

    # Add the split column groups.
    for split_manifest_filepath in split_manifest_filepaths:
      with open_file(split_manifest_filepath) as f:
        split_manifest = SplitManifest.parse_raw(f.read())

      column_groups.append(
          ColumnGroup(files=split_manifest.files,
                      splitter_name=split_manifest.splitter.splitter_name,
                      original_column_path=split_manifest.enriched_path,
                      data_schema=split_manifest.data_schema))

    return column_groups

  @override
  def manifest(self) -> DatasetManifest:
    merged_schema = Schema(fields={**self._source_manifest.data_schema.fields})

    column_groups = self._column_groups(self._column_signal_manifest_files(),
                                        self._column_split_manifest_files())
    for column_group in column_groups:
      # The source schema is already merged.
      if column_group.signal_name is None and column_group.splitter_name is None:
        continue
      if column_group.original_column_path is None:
        print(f'Column group {column_group} has no original column path.')
        continue

      original_path = column_group.original_column_path
      if isinstance(original_path, str):
        normalized_path = [original_path]
      else:
        normalized_path = cast(list[str], original_path)

      original_top_level_column = normalized_path[0]
      enricher_name = column_group.signal_name or column_group.splitter_name
      if not enricher_name:
        raise ValueError(
            'One of column_group.signal_name or column_group.splitter_name must be defined.')
      top_level_column_name = self._top_level_col_name(column_group.original_column_path,
                                                       enricher_name)
      merged_schema.fields[top_level_column_name] = column_group.data_schema.fields[
          original_top_level_column]

    return DatasetManifest(namespace=self.namespace,
                           dataset_name=self.dataset_name,
                           data_schema=merged_schema)

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
  def compute_embedding_index(self, embedding: EmbeddingId, columns: Sequence[ColumnId]) -> None:
    cols = [column_from_identifier(column) for column in columns]

    rows = self.select_rows(columns=[Column(UUID_COLUMN)] + cols, limit=None)

    keys = map(lambda row: row[UUID_COLUMN], rows)
    for column in cols:
      data = map(lambda row: row[column.alias], rows)

      if isinstance(column.feature, Column):
        raise ValueError(
            f'Cannot compute an embedding index for {column} as it is not a leaf feature.')

      self._embedding_indexer.compute_embedding_index(column=column.feature,
                                                      embedding=embedding,
                                                      keys=keys,
                                                      data=data)

  @override
  def compute_signal_columns(self, signal: Signal, columns: Sequence[ColumnId]) -> None:
    cols = [column_from_identifier(column) for column in columns]

    signal_fields = signal.fields()

    for column in cols:
      if isinstance(column.feature, Column):
        raise ValueError(f'Cannot compute a signal for {column} as it is not a leaf feature.')

      source_path = normalize_path(column.feature)
      signal_schema = create_enriched_schema(source_schema=self._source_manifest.data_schema,
                                             enrich_paths=[source_path],
                                             enrich_fields=signal_fields)

      if signal.embedding_based:
        raise ValueError('Embedding based signal cannot yet be computed.')
      else:
        leaf_alias = 'text'

        with DebugTimer(f'"_select_leafs" over "{source_path}"'):
          select_leafs_result = self._select_leafs(path=source_path, leaf_alias=leaf_alias)
          leafs_df = select_leafs_result.duckdb_result.to_df()

        with DebugTimer(f'"compute" for signal "{signal.name}" over "{source_path}"'):
          signal_outputs = signal.compute(data=leafs_df[leaf_alias])

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
                                         enriched_path=source_path)
        signal_manifest_filepath = os.path.join(
            self.dataset_path,
            signal_manifest_filename(column_name=column.alias, signal_name=signal.name))
        with open_file(signal_manifest_filepath, 'w') as f:
          f.write(signal_manifest.json())
        log(f'Wrote signal manifest to {signal_manifest_filepath}')

  @override
  def compute_split_column(self, splitter: TextSplitter, columns: Sequence[ColumnId]) -> None:
    cols = [column_from_identifier(column) for column in columns]
    for column in cols:
      if isinstance(column.feature, Column):
        raise ValueError(f'Cannot compute a signal for {column} as it is not a leaf feature.')

      source_path = normalize_path(column.feature)
      split_schema = create_enriched_schema(source_schema=self._source_manifest.data_schema,
                                            enrich_paths=[source_path],
                                            enrich_fields=SPLITS_FIELDS)
      with DebugTimer(f'"_select_leafs" over "{source_path}"'):
        leaf_alias = 'text'
        select_leafs_result = self._select_leafs(path=source_path, leaf_alias=leaf_alias)
        leafs_df = select_leafs_result.duckdb_result.to_df()

      split_items: list[Item] = []
      with DebugTimer(f'"split" for splitter "{splitter.name}" over "{source_path}"'):
        for text in leafs_df[leaf_alias]:
          splits = splitter.split(text=text)
          split_items.append(item_from_spans(splits))

      # Use the repeated indices to generate the correct output structure.
      if select_leafs_result.repeated_idxs_col:
        repeated_idxs = leafs_df[select_leafs_result.repeated_idxs_col]

      # Repeat "None" if there are no repeated indices without allocating an array. This happens
      # when the object is a simple structure.
      repeated_idxs_iter: Iterable[Optional[list[int]]] = (
          itertools.repeat(None) if not select_leafs_result.repeated_idxs_col else repeated_idxs)

      enriched_split_items = list(
          make_enriched_items(source_path=source_path,
                              row_ids=leafs_df[UUID_COLUMN],
                              leaf_items=split_items,
                              repeated_idxs=repeated_idxs_iter))

      split_out_prefix = split_parquet_prefix(column_name=column.alias, splitter_name=splitter.name)
      parquet_filename, _ = write_items_to_parquet(items=enriched_split_items,
                                                   output_dir=self.dataset_path,
                                                   schema=split_schema,
                                                   filename_prefix=split_out_prefix,
                                                   shard_index=0,
                                                   num_shards=1)
      split_manifest = SplitManifest(files=[parquet_filename],
                                     data_schema=split_schema,
                                     splitter=splitter,
                                     enriched_path=source_path)
      split_manifest_filepath = os.path.join(
          self.dataset_path,
          split_manifest_filename(column_name=column.alias, splitter_name=splitter.name))
      with open_file(split_manifest_filepath, 'w') as f:
        f.write(split_manifest.json())
      log(f'Wrote split manifest to {split_manifest_filepath}')

  def _select_leafs(self, path: Path, leaf_alias: str) -> SelectLeafsResult:
    path = normalize_path(path)
    for path_component in path[0:-1]:
      if is_repeated_path_part(path_component):
        raise ValueError(
            f'Outer repeated leafs are not yet supported in _select_leafs. Requested Path: {path}')

    leaf_components: list[str] = []
    for leaf_component in path:
      # Ignore repeated paths. They will be added via unnest for inner-most repeated.s
      if is_repeated_path_part(leaf_component):
        continue
      leaf_components.append(f'"{leaf_component}"')

    leaf_col = '.'.join(leaf_components)

    is_inner_repeated = is_repeated_path_part(path[-1])

    repeated_indices_col: Optional[str] = None
    if not is_inner_repeated:
      leaf_select = f'{leaf_col} as {leaf_alias}'
    else:
      repeated_indices_col = 'repeated_indices'
      # Zip the values of the array with the indices into the array so we can construct the signal
      # item.
      leaf_select = f"""
        UNNEST({leaf_col}) as {leaf_alias},
        UNNEST(RANGE(ARRAY_LENGTH({leaf_col}))) as {repeated_indices_col}
      """

    query = f"""
    SELECT {UUID_COLUMN}, {leaf_select}
    FROM t
    """
    return SelectLeafsResult(duckdb_result=self._query(query),
                             repeated_idxs_col=repeated_indices_col)

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
      select_queries.append(f'"{self._path_to_col(column.feature)}" AS {column.alias}')

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

  def _path_to_col(self, path: Path) -> str:
    """Convert a path to a column name."""
    if isinstance(path, str):
      return path
    return '.'.join([str(path_comp) for path_comp in path])

  def _top_level_col_name(self, path: Path, enricher_name: str) -> str:
    column_name = self._path_to_col(path)
    if column_name.endswith('.*'):
      # Remove the trailing .* from the column name.
      column_name = column_name[:-2]

    return f'{column_name}.{enricher_name}'


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

  data_schema: Schema
  signal: Signal

  # The column path that this signal is derived from.
  enriched_path: Path

  @validator('signal', pre=True)
  def parse_signal(cls, signal: dict) -> Signal:
    """Parse a signal to its specific subclass instance."""
    return resolve_signal(signal)


class SplitManifest(BaseModel):
  """The manifest that describes a split computation including schema and parquet files."""
  # List of a parquet filepaths storing the data. The paths are relative to the manifest
  files: list[str]

  data_schema: Schema
  splitter: TextSplitter

  # The column path that this split is derived from.
  enriched_path: Path

  @validator('splitter', pre=True)
  def parse_splitter(cls, splitter: dict) -> TextSplitter:
    """Parse a splitter to its specific subclass instance."""
    return resolve_splitter(splitter)
