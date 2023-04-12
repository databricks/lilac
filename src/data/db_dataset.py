"""The interface for the database."""
import abc
import datetime
import enum
from typing import Any, Iterable, Iterator, Optional, Sequence, Union

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

from ..embeddings.embedding_registry import EmbeddingId
from ..schema import Item, Path, PathTuple, Schema, path_to_alias
from ..signals.signal import Signal

# Threshold for rejecting certain queries (e.g. group by) for columns with large cardinality.
TOO_MANY_DISTINCT = 10_000


class SelectRowsResult():
  """The result of a select rows query."""

  def __init__(self, rows: Iterable[Item]) -> None:
    """Initialize the result."""
    self.rows = rows

  def __iter__(self) -> Iterator:
    return iter(self.rows)


class SelectGroupsResult():
  """The result of a select groups query."""

  @abc.abstractmethod
  def __iter__(self) -> Iterator:
    pass

  @abc.abstractmethod
  def to_df(self) -> pd.DataFrame:
    """Convert the result to a pandas DataFrame."""
    pass


class StatsResult(BaseModel):
  """The result of a stats() query."""
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


class Column(BaseModel):
  """A column in the dataset DB."""
  # The feature points to another column if this is a transformation of that column.
  feature: Union[Path, 'Column']
  alias: str  # This is the renamed column during querying and response.

  # Defined when the feature is another column.
  transform: Optional[Transform]

  def __init__(self, feature: Union[Path, 'Column'], alias: Optional[str] = None, **kwargs: Any):
    """Initialize a column. We override __init__ to allow positional arguments for brevity."""
    if not alias:
      if isinstance(feature, Column):
        raise ValueError('Please define an alias for the column when it has a transform.')
      if isinstance(feature, str):
        alias = feature
      else:
        alias = path_to_alias(feature)

    super().__init__(feature=feature, alias=alias, **kwargs)


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


class ConceptTransform(Transform):
  """Computes a concept transformation over a field."""
  namespace: str
  concept_name: str
  embedding_name: str


class BucketizeTransform(Transform):
  """Bucketizes the input float into descrete integer buckets."""
  bins: list[float]


def Bucketize(column: Column, bins: list[float]) -> Column:
  """Bucketize a column."""
  return Column(feature=column, transform=BucketizeTransform(bins=bins))


FeatureValue = Union[StrictInt, StrictFloat, StrictBool, StrictStr, StrictBytes]
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
  def columns(self) -> list[Column]:
    """Return the list of columns supported for the dataset."""
    pass

  @abc.abstractmethod
  def compute_embedding_index(self, embedding: EmbeddingId, column: ColumnId) -> None:
    """Compute an embedding index for a column."""
    pass

  @abc.abstractmethod
  def compute_signal_columns(self,
                             signal: Signal,
                             column: ColumnId,
                             signal_column_name: Optional[str] = None) -> str:
    """Compute a signal for a column.

    Args:
      signal: The signal to compute over the given columns.
      column: The column to compute the signal on.
      signal_column_name: The name of the result signal columns. This acts as a namespace for
        the set of columns the signal produces.

    Returns
      The name of the result columns.
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
                  sort_by: Optional[list[str]] = None,
                  sort_order: Optional[SortOrder] = SortOrder.DESC,
                  limit: Optional[int] = 100,
                  offset: Optional[int] = 0) -> SelectRowsResult:
    """Select grouped columns to power a histogram.

    Args:
      columns: The columns to select. A column is an instance of `Column` which can either
        define a path to a feature, or a column with an applied Transform, e.g. a Concept.
      filters: The filters to apply to the query.
      sort_by: An ordered list of what to sort by. When defined, this is a list of aliases of column
        names defined by the "alias" field in Column. If no alias is provided for a column, an
        automatic alias is generated by combining each path element with a "."
        For example: e.g. ('person', 'name') => person.name. For columns that are transform columns,
        an alias must be provided explicitly.
      sort_order: The sort order.
      limit: The maximum number of rows to return.
      offset: The offset to start returning rows from.

    Returns
      A SelectRowsResult iterator with rows of `Item`s.
    """
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
