"""The interface for the database."""
import abc
import datetime
import enum
from typing import Any, Iterator, Optional, Sequence, Union

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

from ..schema import VALUE_KEY, Path, PathTuple, Schema, normalize_path
from ..signals.concept_scorer import ConceptScoreSignal
from ..signals.signal import Signal
from ..signals.signal_registry import resolve_signal
from ..tasks import TaskId

# Threshold for rejecting certain queries (e.g. group by) for columns with large cardinality.
TOO_MANY_DISTINCT = 10_000


class SelectRowsResult():
  """The result of a select rows query."""

  def __init__(self, df: pd.DataFrame) -> None:
    """Initialize the result."""
    self._df = df

  def __iter__(self) -> Iterator:
    return (row.to_dict() for _, row in self._df.iterrows())

  def df(self) -> pd.DataFrame:
    """Convert the result to a pandas DataFrame."""
    return self._df


class SelectGroupsResult():
  """The result of a select groups query."""

  @abc.abstractmethod
  def __iter__(self) -> Iterator:
    pass

  @abc.abstractmethod
  def df(self) -> pd.DataFrame:
    """Convert the result to a pandas DataFrame."""
    pass


class StatsResult(BaseModel):
  """The result of a stats() query."""
  # The number of leaf values.
  total_count: int
  # The approximate number of distinct leaf values.
  approx_count_distinct: int

  # Defined for ordinal features.
  min_val: Optional[Union[float, datetime.date, datetime.datetime]]
  max_val: Optional[Union[float, datetime.date, datetime.datetime]]

  # Defined for text features.
  avg_text_length: Optional[float]


class MediaResult(BaseModel):
  """The result of a media() query."""
  data: bytes


class Comparison(str, enum.Enum):
  """The comparison operator between a column and a feature value."""
  EQUALS = 'equals'
  NOT_EQUAL = 'not_equal'
  GREATER = 'greater'
  GREATER_EQUAL = 'greater_equal'
  LESS = 'less'
  LESS_EQUAL = 'less_equal'
  IN = 'in'


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


class Transform(BaseModel):
  """The base class for a feature transform, e.g. bucketization or concept."""
  pass


class BucketizeTransform(Transform):
  """Bucketizes the input float into descrete integer buckets."""
  bins: list[float]


class SignalTransform(Transform):
  """Computes a signal transformation over a field."""
  signal: Union[ConceptScoreSignal, Signal]

  class Config:
    smart_union = True

  @validator('signal', pre=True)
  def parse_signal(cls, signal: dict) -> Union[ConceptScoreSignal, Signal]:
    """Parse a signal to its specific subclass instance."""
    return resolve_signal(signal)


class Column(BaseModel):
  """A column in the dataset DB."""
  feature: PathTuple
  alias: Optional[str]  # This is the renamed column during querying and response.

  # Defined when the feature is another column.
  transform: Optional[Union[BucketizeTransform, SignalTransform]] = None

  class Config:
    smart_union = True

  def __init__(self,
               feature: Path,
               alias: Optional[str] = None,
               transform: Optional[Transform] = None,
               **kwargs: Any):
    """Initialize a column. We override __init__ to allow positional arguments for brevity."""
    if isinstance(feature, str):
      feature = (feature,)

    super().__init__(feature=feature, alias=alias, transform=transform, **kwargs)


ColumnId = Union[Path, Column]

# A bin can be a float, or a tuple of (label, float).


class NamedBins(BaseModel):
  """Named bins where each boundary has a label."""
  bins: list[float]
  # Labels is one more than bins. E.g. given bins [1, 2, 3], we have 4 labels (≤1, 1-2, 2-3, >3).
  labels: Optional[list[str]]

  @validator('labels')
  def labels_is_one_more_than_bins(cls, labels: Optional[list[str]],
                                   values: dict[str, Any]) -> Optional[list[str]]:
    """Validate that the labels is one more than the bins."""
    if not labels:
      return None
    if len(labels) != len(values['bins']) + 1:
      raise ValueError('The number of labels must be one more than the number of bins.')
    return labels


Bins = Union[list[float], NamedBins]


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
    result = column.copy()
  else:
    result = Column(feature=column)
  # We normalize the feature to always be a path.
  if isinstance(result.feature, (str, int)):
    result.feature = (result.feature,)

  return result


def Bucketize(column: ColumnId, bins: list[float]) -> Column:
  """Bucketize a column."""
  column = column_from_identifier(column)
  return Column(feature=column.feature, transform=BucketizeTransform(bins=bins))


def SignalUDF(signal: Signal, column: ColumnId, alias: Optional[str] = None) -> Column:
  """Execute the signal as a user-defined function on the selected rows."""
  result_column = Column(
    feature=column_from_identifier(column).feature, transform=SignalTransform(signal=signal))
  if alias:
    result_column.alias = alias
  return result_column


FeatureValue = Union[StrictInt, StrictFloat, StrictBool, StrictStr, StrictBytes, list[StrictStr]]
FilterTuple = tuple[Union[Path, Column], Comparison, FeatureValue]


class Filter(BaseModel):
  """A filter on a column."""
  path: PathTuple
  comparison: Comparison
  value: FeatureValue


FilterLike = Union[Filter, FilterTuple]


class DatasetDB(abc.ABC):
  """The database implementation to query a dataset."""

  def __init__(self, namespace: str, dataset_name: str):
    """Initialize a dataset.

    Args:
      namespace: The dataset namespace.
      dataset_name: The dataset name.
    """
    self.namespace = namespace
    self.dataset_name = dataset_name

  @abc.abstractmethod
  def manifest(self) -> DatasetManifest:
    """Return the manifest for the dataset."""
    pass

  @abc.abstractmethod
  def compute_signal(self,
                     signal: Signal,
                     column: ColumnId,
                     task_id: Optional[TaskId] = None) -> None:
    """Compute a signal for a column.

    Args:
      signal: The signal to compute over the given columns.
      column: The column to compute the signal on.
      task_id: The TaskManager `task_id` for this process run. This is used to update the progress
        of the task.
    """
    pass

  @abc.abstractmethod
  def select_groups(self,
                    leaf_path: Path,
                    filters: Optional[Sequence[FilterLike]] = None,
                    sort_by: Optional[GroupsSortBy] = None,
                    sort_order: Optional[SortOrder] = SortOrder.DESC,
                    limit: Optional[int] = None,
                    bins: Optional[Bins] = None) -> SelectGroupsResult:
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
                  filters: Optional[Sequence[FilterLike]] = None,
                  sort_by: Optional[Sequence[Path]] = None,
                  sort_order: Optional[SortOrder] = SortOrder.DESC,
                  limit: Optional[int] = 100,
                  offset: Optional[int] = 0,
                  task_id: Optional[TaskId] = None,
                  resolve_span: bool = False,
                  combine_columns: bool = False) -> SelectRowsResult:
    """Select grouped columns to power a histogram.

    Args:
      columns: The columns to select. A column is an instance of `Column` which can either
        define a path to a feature, or a column with an applied Transform, e.g. a Concept. If none,
        it selects all columns.
      filters: The filters to apply to the query.
      sort_by: An ordered list of what to sort by. When defined, this is a list of aliases of column
        names defined by the "alias" field in Column. If no alias is provided for a column, an
        automatic alias is generated by combining each path element with a "."
        For example: e.g. ('person', 'name') => person.name. For columns that are transform columns,
        an alias must be provided explicitly.
      sort_order: The sort order.
      limit: The maximum number of rows to return.
      offset: The offset to start returning rows from.
      task_id: The TaskManager `task_id` for this process run. This is used to update the progress.
      resolve_span: Whether to resolve the span of the row.
      combine_columns: Whether to combine columns into a single object. The object will be pruned
        to only include sub-fields that correspond to the requested columns.

    Returns
      A SelectRowsResult iterator with rows of `Item`s.
    """
    pass

  @abc.abstractmethod
  def select_rows_schema(self,
                         columns: Optional[Sequence[ColumnId]] = None,
                         combine_columns: bool = False) -> Schema:
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


def make_parquet_id(signal: Signal, source_path: PathTuple) -> str:
  """Return a unique identifier for this parquet table."""
  # Don't use the VALUE_KEY as part of the parquet id to reduce the size of paths.
  path = source_path[:-1] if source_path[-1] == VALUE_KEY else source_path
  column_alias = '.'.join(map(str, path))
  if column_alias.endswith('.*'):
    # Remove the trailing .* from the column name.
    column_alias = column_alias[:-2]

  return f'{signal.key()}({column_alias})'


def val(path: Path) -> PathTuple:
  """Returns the value at a path."""
  if path[-1] == VALUE_KEY:
    raise ValueError(f'Path "{path}" already is a value path.')
  return (*normalize_path(path), VALUE_KEY)
