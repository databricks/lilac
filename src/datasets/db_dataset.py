"""The interface for the database."""
import abc
import enum
from typing import Any, Iterable, Iterator, Optional, Sequence, Union

import pandas as pd
from pydantic import BaseModel

from ..embeddings.embedding_registry import EmbeddingId
from ..schema import Item, Path, Schema, path_to_alias
from ..signals.signal import Signal


class SelectRowsResult():
  """The result of a select rows query."""

  def __init__(self, rows: Iterable[Item]) -> None:
    """Initialize the result."""
    self.rows = rows

  def __iter__(self) -> Iterator:
    return iter(self.rows)


class Comparison(str, enum.Enum):
  """The comparison operator between a column and a feature value."""
  EQUALS = '='
  NOT_EQUAL = '!='
  GREATER = '>'
  GREATER_EQUAL = '>='
  LESS = '<'
  LESS_EQUAL = '<='


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


class DatasetManifest(BaseModel):
  """The manifest for a dataset."""
  namespace: str
  dataset_name: str
  data_schema: Schema


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


FeatureValue = Union[int, float, bool, str]
Filter = tuple[Column, Comparison, FeatureValue]


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
  def compute_embedding_index(self, embedding: EmbeddingId, columns: Sequence[ColumnId]) -> None:
    """Compute an embedding index for a set of columns."""
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
                    column_ids: Optional[Sequence[ColumnId]] = None,
                    filters: Optional[Sequence[Filter]] = None,
                    sort_by: Optional[GroupsSortBy] = None,
                    sort_order: Optional[SortOrder] = SortOrder.DESC,
                    limit: Optional[int] = 100) -> pd.DataFrame:
    """Select grouped columns to power a histogram.

    Args:
      column_ids: The columns to select. A column is an instance of `Column` which can either
        define a path to a feature, or a column with an applied Transform, e.g. a Concept.
      filters: The filters to apply to the query.
      sort_by: What to sort by, either "count" or "value".
      sort_order: The sort order.
      limit: The maximum number of rows to return.

    Returns
      A dataframe with counts for each selected columnm, applying the filters.
    """
    pass

  @abc.abstractmethod
  def select_rows(self,
                  columns: Optional[Sequence[ColumnId]] = None,
                  filters: Optional[Sequence[Filter]] = None,
                  sort_by: Optional[list[str]] = None,
                  sort_order: Optional[SortOrder] = SortOrder.DESC,
                  limit: Optional[int] = 100) -> SelectRowsResult:
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

    Returns
      A SelectRowsResult iterator with rows of `Item`s.
    """
    pass
