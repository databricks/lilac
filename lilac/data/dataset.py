"""The interface for the database."""
from __future__ import annotations

import abc
import enum
import pathlib
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Any, Iterator, Literal, Optional, Sequence, Union

import pandas as pd
from pydantic import (
  BaseModel,
  StrictBool,
  StrictBytes,
  StrictFloat,
  StrictInt,
  StrictStr,
  validator,
)
from typing_extensions import TypeAlias

from lilac.signals.concept_scorer import ConceptSignal

from ..auth import UserInfo
from ..config import DatasetConfig, DatasetSettings, DatasetUISettings
from ..schema import (
  PATH_WILDCARD,
  ROWID,
  VALUE_KEY,
  Bin,
  DataType,
  Path,
  PathTuple,
  Schema,
  normalize_path,
)
from ..signal import Signal, TextEmbeddingSignal, get_signal_by_type, resolve_signal
from ..tasks import TaskStepId

# Threshold for rejecting certain queries (e.g. group by) for columns with large cardinality.
TOO_MANY_DISTINCT = 500_000
SAMPLE_AVG_TEXT_LENGTH = 1000
MAX_TEXT_LEN_DISTINCT_COUNT = 250


class SelectRowsResult:
  """The result of a select rows query."""

  def __init__(self, df: pd.DataFrame, total_num_rows: int) -> None:
    """Initialize the result."""
    self._df = df
    self.total_num_rows = total_num_rows

  def __iter__(self) -> Iterator:
    return (row.to_dict() for _, row in self._df.iterrows())

  def df(self) -> pd.DataFrame:
    """Convert the result to a pandas DataFrame."""
    return self._df


class StatsResult(BaseModel):
  """The result of a stats() query."""
  path: PathTuple
  # The number of leaf values.
  total_count: int
  # The approximate number of distinct leaf values.
  approx_count_distinct: int

  # Defined for ordinal features.
  min_val: Optional[Union[float, datetime]] = None
  max_val: Optional[Union[float, datetime]] = None

  # Defined for text features.
  avg_text_length: Optional[float] = None


class MediaResult(BaseModel):
  """The result of a media() query."""
  data: bytes


BinaryOp = Literal['equals', 'not_equal', 'greater', 'greater_equal', 'less', 'less_equal']
UnaryOp = Literal['exists']
ListOp = Literal['in']

BINARY_OPS = set(['equals', 'not_equal', 'greater', 'greater_equal', 'less', 'less_equal'])
UNARY_OPS = set(['exists'])
LIST_OPS = set(['in'])

SearchType = Union[Literal['keyword'], Literal['semantic'], Literal['concept']]


class SortOrder(str, enum.Enum):
  """The sort order for a database query."""
  DESC = 'DESC'
  ASC = 'ASC'


class GroupsSortBy(str, enum.Enum):
  """The sort for groups queries.

  Either "count" which sorts by the count of feature value, or "value" which sorts by the
  feature value itself.
  """
  COUNT = 'count'
  VALUE = 'value'


class SortResult(BaseModel):
  """The information about what is sorted after combining searches and explicit sorts."""
  # The column that was sorted.
  path: PathTuple
  # The sort order.
  order: SortOrder
  # The alias of the column if it was aliased.
  alias: Optional[str] = None
  # The search index if the sort is by a search.
  search_index: Optional[int] = None


class SearchResultInfo(BaseModel):
  """The resulting sort order returned by the select rows schema."""
  # The input path to the search.
  search_path: PathTuple
  # The resulting column that was searched.
  result_path: PathTuple
  # The alias of the UDF.
  alias: Optional[str] = None


class SelectRowsSchemaUDF(BaseModel):
  """The UDF for a select rows schema query."""
  path: PathTuple
  alias: Optional[str] = None


class SelectRowsSchemaResult(BaseModel):
  """The result of a select rows schema query."""
  data_schema: Schema
  udfs: list[SelectRowsSchemaUDF] = []
  search_results: list[SearchResultInfo] = []
  sorts: Optional[list[SortResult]] = None


class Column(BaseModel):
  """A column in the dataset."""
  path: PathTuple
  alias: Optional[str] = None  # This is the renamed column during querying and response.

  # Defined when the feature is another column.
  signal_udf: Optional[Signal] = None

  class Config:
    smart_union = True

  def __init__(self,
               path: Path,
               alias: Optional[str] = None,
               signal_udf: Optional[Signal] = None,
               **kwargs: Any):
    """Initialize a column. We override __init__ to allow positional arguments for brevity."""
    super().__init__(path=normalize_path(path), alias=alias, signal_udf=signal_udf, **kwargs)

  @validator('signal_udf', pre=True)
  def parse_signal_udf(cls, signal_udf: Optional[dict]) -> Optional[Signal]:
    """Parse a signal to its specific subclass instance."""
    if not signal_udf:
      return None
    return resolve_signal(signal_udf)


ColumnId = Union[Path, Column]


class DatasetManifest(BaseModel):
  """The manifest for a dataset."""
  namespace: str
  dataset_name: str
  data_schema: Schema
  # Number of items in the dataset.
  num_items: int


def column_from_identifier(column: ColumnId) -> Column:
  """Create a column from a column identifier."""
  if isinstance(column, Column):
    return column.copy()
  return Column(path=column)


FeatureValue = Union[StrictInt, StrictFloat, StrictBool, StrictStr, StrictBytes, datetime]
FeatureListValue = list[StrictStr]
BinaryFilterTuple = tuple[Path, BinaryOp, FeatureValue]
ListFilterTuple = tuple[Path, ListOp, FeatureListValue]
UnaryFilterTuple = tuple[Path, UnaryOp]

FilterOp = Union[BinaryOp, UnaryOp, ListOp]


class SelectGroupsResult(BaseModel):
  """The result of a select groups query."""
  too_many_distinct: bool
  counts: list[tuple[Optional[FeatureValue], int]]
  bins: Optional[list[Bin]] = None


class Filter(BaseModel):
  """A filter on a column."""
  path: PathTuple
  op: FilterOp
  value: Optional[Union[FeatureValue, FeatureListValue]] = None


FilterLike: TypeAlias = Union[Filter, BinaryFilterTuple, UnaryFilterTuple, ListFilterTuple]

SearchValue = StrictStr


class KeywordSearch(BaseModel):
  """A keyword search query on a column."""
  path: Path
  query: SearchValue
  type: Literal['keyword'] = 'keyword'


class SemanticSearch(BaseModel):
  """A semantic search on a column."""
  path: Path
  query: SearchValue
  embedding: str
  type: Literal['semantic'] = 'semantic'


class ConceptSearch(BaseModel):
  """A concept search query on a column."""
  path: Path
  concept_namespace: str
  concept_name: str
  embedding: str
  type: Literal['concept'] = 'concept'


Search = Union[ConceptSearch, SemanticSearch, KeywordSearch]


class Dataset(abc.ABC):
  """The database implementation to query a dataset."""

  namespace: str
  dataset_name: str

  def __init__(self, namespace: str, dataset_name: str):
    """Initialize a dataset.

    Args:
      namespace: The dataset namespace.
      dataset_name: The dataset name.
    """
    self.namespace = namespace
    self.dataset_name = dataset_name

  @abc.abstractmethod
  def delete(self) -> None:
    """Deletes the dataset."""
    pass

  @abc.abstractmethod
  def manifest(self) -> DatasetManifest:
    """Return the manifest for the dataset."""
    pass

  @abc.abstractmethod
  def config(self) -> DatasetConfig:
    """Return the dataset config for this dataset."""
    pass

  @abc.abstractmethod
  def settings(self) -> DatasetSettings:
    """Return the persistent settings for the dataset."""
    pass

  @abc.abstractmethod
  def update_settings(self, settings: DatasetSettings) -> None:
    """Update the settings for the dataset."""
    pass

  @abc.abstractmethod
  def compute_signal(self,
                     signal: Signal,
                     path: Path,
                     task_step_id: Optional[TaskStepId] = None) -> None:
    """Compute a signal for a column.

    Args:
      signal: The signal to compute over the given columns.
      path: The leaf path to compute the signal on.
      task_step_id: The TaskManager `task_step_id` for this process run. This is used to update the
        progress of the task.
    """
    pass

  def compute_embedding(self,
                        embedding: str,
                        path: Path,
                        task_step_id: Optional[TaskStepId] = None) -> None:
    """Compute an embedding for a given field path."""
    signal = get_signal_by_type(embedding, TextEmbeddingSignal)()
    self.compute_signal(signal, path, task_step_id)

  def compute_concept(self,
                      namespace: str,
                      concept_name: str,
                      embedding: str,
                      path: Path,
                      task_step_id: Optional[TaskStepId] = None) -> None:
    """Compute concept scores for a given field path."""
    signal = ConceptSignal(namespace=namespace, concept_name=concept_name, embedding=embedding)
    self.compute_signal(signal, path, task_step_id)

  @abc.abstractmethod
  def delete_signal(self, signal_path: Path) -> None:
    """Delete a computed signal from the dataset.

    Args:
      signal_path: The path holding the computed data of the signal.
    """
    pass

  @abc.abstractmethod
  def select_groups(
      self,
      leaf_path: Path,
      filters: Optional[Sequence[FilterLike]] = None,
      sort_by: Optional[GroupsSortBy] = None,
      sort_order: Optional[SortOrder] = SortOrder.DESC,
      limit: Optional[int] = None,
      bins: Optional[Union[Sequence[Bin], Sequence[float]]] = None) -> SelectGroupsResult:
    """Select grouped columns to power a histogram.

    Args:
      leaf_path: The leaf path to group by. The path can be a dot-seperated string path, or a tuple
                 of fields.
      filters: The filters to apply to the query.
      sort_by: What to sort by, either "count" or "value".
      sort_order: The sort order.
      limit: The maximum number of rows to return.
      bins: The bins to use when bucketizing a float column.

    Returns
      A `SelectGroupsResult` iterator where each row is a group.
    """
    raise NotImplementedError

  @abc.abstractmethod
  def select_rows(self,
                  columns: Optional[Sequence[ColumnId]] = None,
                  searches: Optional[Sequence[Search]] = None,
                  filters: Optional[Sequence[FilterLike]] = None,
                  sort_by: Optional[Sequence[Path]] = None,
                  sort_order: Optional[SortOrder] = SortOrder.DESC,
                  limit: Optional[int] = 100,
                  offset: Optional[int] = 0,
                  task_step_id: Optional[TaskStepId] = None,
                  resolve_span: bool = False,
                  combine_columns: bool = False,
                  user: Optional[UserInfo] = None) -> SelectRowsResult:
    """Select a set of rows that match the provided filters, analogous to SQL SELECT.

    Args:
      columns: The columns to select. A column is an instance of `Column` which can either
        define a path to a feature, or a column with an applied Transform, e.g. a Concept. If none,
        it selects all columns.
      searches: The searches to apply to the query.
      filters: The filters to apply to the query.
      sort_by: An ordered list of what to sort by. When defined, this is a list of aliases of column
        names defined by the "alias" field in Column. If no alias is provided for a column, an
        automatic alias is generated by combining each path element with a "."
        For example: e.g. ('person', 'name') => person.name. For columns that are transform columns,
        an alias must be provided explicitly. When sorting by a (nested) list of values, the sort
        takes the minumum value when `sort_order` is `ASC`, and the maximum value when `sort_order`
        is `DESC`.
      sort_order: The sort order.
      limit: The maximum number of rows to return.
      offset: The offset to start returning rows from.
      task_step_id: The TaskManager `task_step_id` for this process run. This is used to update the
        progress.
      resolve_span: Whether to resolve the span of the row.
      combine_columns: Whether to combine columns into a single object. The object will be pruned
        to only include sub-fields that correspond to the requested columns.
      user: The authenticated user, if auth is enabled and the user is logged in. This is used to
        apply ACL to the query, especially for concepts.

    Returns
      A `SelectRowsResult` iterator with rows of `Item`s.
    """
    pass

  @abc.abstractmethod
  def select_rows_schema(self,
                         columns: Optional[Sequence[ColumnId]] = None,
                         sort_by: Optional[Sequence[Path]] = None,
                         sort_order: Optional[SortOrder] = SortOrder.DESC,
                         searches: Optional[Sequence[Search]] = None,
                         combine_columns: bool = False) -> SelectRowsSchemaResult:
    """Returns the schema of the result of `select_rows` above with the same arguments."""
    pass

  @abc.abstractmethod
  def stats(self, leaf_path: Path) -> StatsResult:
    """Compute stats for a leaf path.

    Args:
      leaf_path: The leaf path to compute stats for.

    Returns
      A StatsResult.
    """
    pass

  @abc.abstractmethod
  def media(self, item_id: str, leaf_path: Path) -> MediaResult:
    """Return the media for a leaf path.

    Args:
      item_id: The item id to get media for.
      leaf_path: The leaf path for the media.

    Returns
      A MediaResult.
    """
    pass

  @abc.abstractmethod
  def to_json(self,
              filepath: Union[str, pathlib.Path],
              jsonl: bool = True,
              columns: Optional[Sequence[ColumnId]] = None) -> None:
    """Export the dataset to a JSON file.

    Args:
      filepath: The path to the file to export to.
      jsonl: Whether to export to JSONL or JSON.
      columns: The columns to export.
    """
    pass

  @abc.abstractmethod
  def to_pandas(self, columns: Optional[Sequence[ColumnId]] = None) -> pd.DataFrame:
    """Export the dataset to a pandas DataFrame.

    Args:
      columns: The columns to export.
    """
    pass

  @abc.abstractmethod
  def to_parquet(self,
                 filepath: Union[str, pathlib.Path],
                 columns: Optional[Sequence[ColumnId]] = None) -> None:
    """Export the dataset to a parquet file.

    Args:
      filepath: The path to the file to export to.
      columns: The columns to export.
    """
    pass

  @abc.abstractmethod
  def to_csv(self,
             filepath: Union[str, pathlib.Path],
             columns: Optional[Sequence[ColumnId]] = None) -> None:
    """Export the dataset to a csv file.

    Args:
      filepath: The path to the file to export to.
      columns: The columns to export.
    """
    pass


def default_settings(dataset: Dataset) -> DatasetSettings:
  """Gets the default settings for a dataset."""
  schema = dataset.manifest().data_schema
  leaf_paths = [
    path for path, field in schema.leafs.items()
    if field.dtype == DataType.STRING and path != (ROWID,)
  ]
  pool = ThreadPoolExecutor()
  stats: list[StatsResult] = list(pool.map(lambda leaf: dataset.stats(leaf), leaf_paths))
  sorted_stats = sorted([stat for stat in stats if stat.avg_text_length],
                        key=lambda stat: stat.avg_text_length or -1.0)
  media_paths: list[PathTuple] = []
  if sorted_stats:
    media_paths = [sorted_stats[-1].path]

  return DatasetSettings(ui=DatasetUISettings(media_paths=media_paths))


def make_parquet_id(signal: Signal,
                    source_path: PathTuple,
                    is_computed_signal: Optional[bool] = False) -> str:
  """Return a unique identifier for this parquet table."""
  # Remove the wildcards from the parquet id since they are implicit.
  path = [*[p for p in source_path if p != PATH_WILDCARD], signal.key(is_computed_signal)]
  # Don't use the VALUE_KEY as part of the parquet id to reduce the size of paths.
  if path[-1] == VALUE_KEY:
    path = path[:-1]
  return '.'.join(path)
