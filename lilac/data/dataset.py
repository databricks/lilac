"""The interface for the database."""
from __future__ import annotations

import abc
import enum
import pathlib
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime
from typing import Any, Callable, Iterable, Iterator, Literal, Optional, Sequence, Union

import numpy as np
import pandas as pd
from datasets import Dataset as HuggingFaceDataset
from pydantic import (
  BaseModel,
  ConfigDict,
  SerializeAsAny,
  StrictBool,
  StrictBytes,
  StrictFloat,
  StrictInt,
  StrictStr,
  field_validator,
)
from pydantic import Field as PydanticField
from typing_extensions import TypeAlias

from ..auth import UserInfo
from ..config import (
  DatasetConfig,
  DatasetSettings,
  DatasetUISettings,
  EmbeddingConfig,
  SignalConfig,
  get_dataset_config,
)
from ..dataset_format import DatasetFormat, DatasetFormatInputSelector
from ..env import get_project_dir
from ..project import read_project_config, update_project_dataset_settings
from ..schema import (
  PATH_WILDCARD,
  ROWID,
  STRING,
  STRING_SPAN,
  Bin,
  EmbeddingInputType,
  Field,
  Item,
  MapFn,
  Path,
  PathKey,
  PathTuple,
  Schema,
  change_const_to_enum,
  normalize_path,
)
from ..signal import (
  Signal,
  TextEmbeddingSignal,
  TopicFn,
  resolve_signal,
)
from ..signals.concept_scorer import ConceptSignal
from ..source import Source, resolve_source
from ..tasks import TaskExecutionType, TaskId

# Threshold for rejecting certain queries (e.g. group by) for columns with large cardinality.
TOO_MANY_DISTINCT = 1_000_000
SAMPLE_AVG_TEXT_LENGTH = 1000
MAX_TEXT_LEN_DISTINCT_COUNT = 250
# Threshold for promoting a column to a media field.
MEDIA_AVG_TEXT_LEN = 150

# Special name for the deleted label.
DELETED_LABEL_NAME = '__deleted__'


class SelectRowsResult:
  """The result of a select rows query."""

  def __init__(self, df: pd.DataFrame, total_num_rows: int) -> None:
    """Initialize the result."""
    self._df = df
    self.total_num_rows = total_num_rows
    self._next_iter: Optional[Iterator] = None

  def __iter__(self) -> Iterator:
    # Replace NaT timestamps with Nones.
    df = self._df.replace({pd.NaT: None})
    return (row.to_dict() for _, row in df.iterrows())

  def __next__(self) -> Item:
    if not self._next_iter:
      self._next_iter = self.__iter__()
    try:
      return next(self._next_iter)
    except StopIteration:
      self._next_iter = None
      raise

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

  # Defined for numeric features.
  min_val: Optional[Union[float, date, datetime]] = None
  max_val: Optional[Union[float, date, datetime]] = None
  # Samples for calculating histogram bins.
  value_samples: list[float] = PydanticField(default=[], exclude=True, repr=False)

  # Defined for text features.
  avg_text_length: Optional[float] = None

  def __eq__(self, other: object) -> bool:
    if not isinstance(other, StatsResult):
      return NotImplemented
    return self.model_dump(exclude={'value_samples'}) == other.model_dump(exclude={'value_samples'})


class MediaResult(BaseModel):
  """The result of a media() query."""

  data: bytes


BinaryOp = Literal['equals', 'not_equal', 'greater', 'greater_equal', 'less', 'less_equal']
StringOp = Literal['length_longer', 'length_shorter', 'ilike', 'regex_matches', 'not_regex_matches']
UnaryOp = Literal['exists', 'not_exists', None]
ListOp = Literal['in', None]
RawSqlOp = Literal['raw_sql']

BINARY_OPS = set(['equals', 'not_equal', 'greater', 'greater_equal', 'less', 'less_equal'])
STRING_OPS = set(['length_longer', 'length_shorter', 'ilike', 'regex_matches', 'not_regex_matches'])
UNARY_OPS = set(['exists', 'not_exists'])
LIST_OPS = set(['in'])
RAW_SQL_OPS = set(['raw_sql'])
ALL_OPS = sorted(BINARY_OPS | STRING_OPS | UNARY_OPS | LIST_OPS | RAW_SQL_OPS)


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

  def __init__(
    self,
    path: Path,
    alias: Optional[str] = None,
    signal_udf: Optional[Signal] = None,
    **kwargs: Any,
  ):
    """Initialize a column. We override __init__ to allow positional arguments for brevity."""
    super().__init__(path=normalize_path(path), alias=alias, signal_udf=signal_udf, **kwargs)

  @field_validator('signal_udf', mode='before')
  @classmethod
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
  source: SerializeAsAny[Source]
  # Number of items in the dataset.
  num_items: int

  # The format of the dataset, automatically inferred.
  dataset_format: Optional[DatasetFormat] = None

  @field_validator('source', mode='before')
  @classmethod
  def parse_source(cls, source: dict) -> Source:
    """Parse a source to its specific subclass instance."""
    return resolve_source(source)


def column_from_identifier(column: ColumnId) -> Column:
  """Create a column from a column identifier."""
  if isinstance(column, Column):
    return column.model_copy()
  return Column(path=column)


FeatureValue = Union[StrictBool, StrictInt, StrictFloat, StrictStr, StrictBytes, datetime]
FeatureListValue = list[StrictStr]
BinaryFilterTuple = tuple[Path, BinaryOp, FeatureValue]
StringFilterTuple = tuple[Path, StringOp, FeatureValue]
ListFilterTuple = tuple[Path, ListOp, FeatureListValue]
UnaryFilterTuple = tuple[Path, UnaryOp]

FilterOp = Union[BinaryOp, StringOp, UnaryOp, ListOp, RawSqlOp]


class SelectGroupsResult(BaseModel):
  """The result of a select groups query."""

  too_many_distinct: bool
  counts: list[tuple[Optional[FeatureValue], int]]
  bins: Optional[list[Bin]] = None


class PivotResultOuterGroup(BaseModel):
  """The outer group of a pivot result."""

  value: Optional[str]
  count: int
  inner: list[tuple[Optional[str], int]]


class PivotResult(BaseModel):
  """The result of a pivot query."""

  outer_groups: list[PivotResultOuterGroup]
  too_many_distinct: bool = False


class Filter(BaseModel):
  """A filter on a column."""

  path: PathTuple
  op: FilterOp = PydanticField(description=f'The type of filter. Available filters are {ALL_OPS}')
  value: Optional[Union[FeatureValue, FeatureListValue]] = None


FilterLike: TypeAlias = Union[
  Filter, BinaryFilterTuple, StringFilterTuple, UnaryFilterTuple, ListFilterTuple
]

SearchValue = StrictStr


class KeywordSearch(BaseModel):
  """A keyword search query on a column."""

  path: Path
  query: SearchValue
  type: Literal['keyword'] = 'keyword'

  model_config = ConfigDict(json_schema_extra=change_const_to_enum('type', 'keyword'))


class SemanticSearch(BaseModel):
  """A semantic search on a column."""

  path: Path
  query: SearchValue
  embedding: str
  type: Literal['semantic'] = 'semantic'
  query_type: EmbeddingInputType = PydanticField(
    title='Query Type',
    default='document',
    description='The input type of the query, used for the query embedding.',
  )

  model_config = ConfigDict(json_schema_extra=change_const_to_enum('type', 'semantic'))


class ConceptSearch(BaseModel):
  """A concept search query on a column."""

  path: Path
  concept_namespace: str
  concept_name: str
  embedding: str
  type: Literal['concept'] = 'concept'

  model_config = ConfigDict(json_schema_extra=change_const_to_enum('type', 'concept'))


class MetadataSearch(BaseModel):
  """A metadata search query on a column."""

  path: Path
  op: FilterOp
  value: Optional[Union[FeatureValue, FeatureListValue]] = None
  type: Literal['metadata'] = 'metadata'

  model_config = ConfigDict(json_schema_extra=change_const_to_enum('type', 'metadata'))


Search = Union[ConceptSearch, SemanticSearch, KeywordSearch, MetadataSearch]


class Dataset(abc.ABC):
  """The database implementation to query a dataset."""

  namespace: str
  dataset_name: str
  project_dir: Union[str, pathlib.Path]

  def __init__(
    self, namespace: str, dataset_name: str, project_dir: Optional[Union[str, pathlib.Path]] = None
  ):
    """Initialize a dataset.

    Args:
      namespace: The dataset namespace.
      dataset_name: The dataset name.
      project_dir: The path to the project directory.
    """
    self.namespace = namespace
    self.dataset_name = dataset_name
    self.project_dir = project_dir or get_project_dir()

  @abc.abstractmethod
  def delete(self) -> None:
    """Deletes the dataset."""
    pass

  @abc.abstractmethod
  def manifest(self) -> DatasetManifest:
    """Return the manifest for the dataset."""
    pass

  def config(self) -> DatasetConfig:
    """Return the dataset config for this dataset."""
    manifest = self.manifest()
    project_config = read_project_config(self.project_dir)
    dataset_config = get_dataset_config(project_config, self.namespace, self.dataset_name)
    if not dataset_config:
      raise ValueError(
        f'Dataset "{self.namespace}/{self.dataset_name}" not found in project config.'
      )

    # Filter out invalid media paths.
    if dataset_config.settings and dataset_config.settings.ui.media_paths:
      dataset_config.settings.ui.media_paths = [
        p for p in dataset_config.settings.ui.media_paths if manifest.data_schema.has_field(p)
      ]

    return dataset_config

  def settings(self) -> DatasetSettings:
    """Return the persistent settings for the dataset."""
    settings = self.config().settings
    return settings or DatasetSettings()

  def update_settings(self, settings: DatasetSettings) -> None:
    """Update the persistent settings for the dataset."""
    update_project_dataset_settings(self.namespace, self.dataset_name, settings, self.project_dir)

  def add_media_field(self, path: Path, markdown: bool = False) -> None:
    """Add a media field to the dataset."""
    settings = self.settings()
    path = normalize_path(path)
    if not self.manifest().data_schema.has_field(path):
      raise ValueError(f'Field "{path}" does not exist in dataset.')
    field = self.manifest().data_schema.get_field(path)
    if field.dtype not in (STRING, STRING_SPAN):
      raise ValueError(f'Field "{path}" is not a string field.')
    if path not in settings.ui.media_paths:
      settings.ui.media_paths.append(path)
    if markdown:
      if path not in settings.ui.markdown_paths:
        settings.ui.markdown_paths.append(path)
    self.update_settings(settings)

  def remove_media_field(self, path: Path) -> None:
    """Remove a media field from the dataset."""
    settings = self.settings()
    path = normalize_path(path)
    if path in settings.ui.media_paths:
      settings.ui.media_paths.remove(path)
    if path in settings.ui.markdown_paths:
      settings.ui.markdown_paths.remove(path)
    self.update_settings(settings)

  @abc.abstractmethod
  def count(
    self,
    filters: Optional[Sequence[FilterLike]] = None,
    limit: Optional[int] = None,
    include_deleted: bool = False,
  ) -> int:
    """Count the number of rows in the dataset.

    Args:
      filters: Filters to apply to the row; only matching rows will be counted.
      limit: Limit the number of rows to count. The returned answer may be smaller than LIMIT,
        if filters reduce the row count to below the limit!
      include_deleted: Whether to include deleted rows in the count.

    Returns:
      The number of rows in the dataset matching the selection parameters.
    """
    pass

  @abc.abstractmethod
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
    """Compute a signal for a column.

    Args:
      signal: The signal to compute over the given columns.
      path: The leaf path to compute the signal on.
      filters: Filters to apply to the row; only matching rows will have the signal computed.
      limit: Limit the number of rows to compute the signal on.
      include_deleted: Whether to include deleted rows in the computation.
      overwrite: Whether to overwrite an existing signal computed at this path.
      task_id: The TaskManager `task_id` for this process run. This is used to update
        the progress of the task.
      use_garden: Whether to run the computation remotely on Lilac Garden.
    """
    pass

  @abc.abstractmethod
  def cluster(
    self,
    input: Union[Path, Callable[[Item], str], DatasetFormatInputSelector],
    output_path: Optional[Path] = None,
    min_cluster_size: int = 5,
    topic_fn: Optional[TopicFn] = None,
    overwrite: bool = False,
    use_garden: bool = False,
    task_id: Optional[TaskId] = None,
    # TODO(0.4.0): colocate with topic_fn.
    category_fn: Optional[TopicFn] = None,
  ) -> None:
    """Compute clusters for a field of the dataset.

    Args:
      input: The path to the text field to cluster, a function that returns a string for each row
        in the dataset, or a `DatasetFormatInputSelector` that is a format-specific input selector,
        like `ShareGPT.human`.
      output_path: The name of the output path to write to. Defaults to the input path + ".cluster".
      min_cluster_size: The minimum number of docs in a cluster.
      topic_fn: A function that returns a topic summary for each cluster. It takes a list of
        (doc, membership_score) tuples and returns a single topic. This is used to compute the topic
        for a given cluster of docs. It defaults to a function that summarizes user's requests.
      overwrite: Whether to overwrite an existing output.
      use_garden: Whether to run the clustering remotely on Lilac Garden.
      task_id: The TaskManager `task_id` for this process run. This is used to update the progress
        of the task.
      category_fn: A function that returns a category for a set of related titles. It takes a list
        of (doc, membership_score) tuples and returns a single category name.

    """
    pass

  @abc.abstractmethod
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
    """Compute an embedding for a given field path.

    Args:
      embedding: The name of the embedding to compute.
      path: The path to compute the embedding on.
      filters: Filters to apply to the row; only matching rows will have the embedding computed.
      limit: Limit the number of rows to compute the embedding on.
      include_deleted: Whether to include deleted rows in the computation.
      overwrite: Whether to overwrite an existing embedding computed at this path.
      task_id: The TaskManager `task_id` for this process run. This is used to update
        the progress of the task.
      use_garden: Whether to run the computation remotely on Lilac Garden.
    """
    pass

  @abc.abstractmethod
  def load_embedding(
    self,
    load_fn: Callable[[Item], Union[np.ndarray, list[Item]]],
    # TODO(nsthorat): Rename this to text_path during the 0.4.0 update.
    index_path: Path,
    embedding: str,
    overwrite: bool = False,
    task_id: Optional[TaskId] = None,
  ) -> None:
    """Loads embeddings from an external source.

    Args:
      load_fn: A function that takes an item and returns an embedding. `load_fn` should return
        either a numpy array for full-document embeddings, or a list of `ll.chunk_embeddings` for
        chunked embeddings.
      index_path: The path to the index to load the embeddings into.
      embedding: The name of the embedding to load under. This should be a registered embedding.
      overwrite: Whether to overwrite an existing embedding.
      task_id: The TaskManager `task_id` for this process run. This is used to update the progress
        of the task.
    """
    pass

  def compute_concept(
    self,
    namespace: str,
    concept_name: str,
    embedding: str,
    path: Path,
    filters: Optional[Sequence[FilterLike]] = None,
    limit: Optional[int] = None,
    include_deleted: bool = False,
    overwrite: bool = False,
    task_id: Optional[TaskId] = None,
  ) -> None:
    """Compute concept scores for a given field path."""
    signal = ConceptSignal(namespace=namespace, concept_name=concept_name, embedding=embedding)
    self.compute_signal(
      signal,
      path,
      filters,
      limit,
      include_deleted,
      overwrite=overwrite,
      task_id=task_id,
    )

  @abc.abstractmethod
  def delete_signal(self, signal_path: Path) -> None:
    """Delete a computed signal from the dataset.

    Args:
      signal_path: The path holding the computed data of the signal.
    """
    pass

  @abc.abstractmethod
  def delete_column(self, path: Path) -> None:
    """Delete a computed column from the dataset.

    Args:
      path: The path of the computed column.
    """
    pass

  @abc.abstractmethod
  def delete_embedding(self, embedding: str, path: Path) -> None:
    """Delete a computed embedding from the dataset.

    Args:
      embedding: The name of the embedding.
      path: The path of the computed embedding.
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
    bins: Optional[Union[Sequence[Bin], Sequence[float]]] = None,
    include_deleted: bool = False,
    searches: Optional[Sequence[Search]] = None,
  ) -> SelectGroupsResult:
    """Select grouped columns to power a histogram.

    Args:
      leaf_path: The leaf path to group by. The path can be a dot-seperated string path, or a tuple
                 of fields.
      filters: The filters to apply to the query.
      sort_by: What to sort by, either "count" or "value".
      sort_order: The sort order.
      limit: The maximum number of rows to return.
      bins: The bins to use when bucketizing a float column.
      include_deleted: Whether to include deleted rows in the query.
      searches: The searches to apply to the query.

    Returns:
      A `SelectGroupsResult` iterator where each row is a group.
    """
    raise NotImplementedError

  @abc.abstractmethod
  def pivot(
    self,
    outer_path: Path,
    inner_path: Path,
    searches: Optional[Sequence[Search]] = None,
    filters: Optional[Sequence[FilterLike]] = None,
    sort_by: Optional[GroupsSortBy] = GroupsSortBy.COUNT,
    sort_order: Optional[SortOrder] = SortOrder.DESC,
  ) -> PivotResult:
    """Generate a pivot table with counts over two fields (outer and inner).

    For each value of `outer_path` in the dataset, the pivot table will contain the count of
    that value, as well as the internal counts of all the values of `inner_path` for the given
    `outer_path` value.

    For example, if `outer_path` is `split=train|test` and `inner_path` is `source=wiki|cc` the
    pivot table will look like:

    ```
    [
      {
        value: 'train', count: 100, inner: [{value: 'wiki', count: 94}, {value: 'cc', count: 6}],
      },
      {
        value: 'test', count: 10, inner: [{value: 'wiki', count: 3}, {value: 'cc', count: 7}],
      },
    ]
    ```
    """
    raise NotImplementedError

  @abc.abstractmethod
  def select_rows(
    self,
    columns: Optional[Sequence[ColumnId]] = None,
    searches: Optional[Sequence[Search]] = None,
    filters: Optional[Sequence[FilterLike]] = None,
    sort_by: Optional[Sequence[Path]] = None,
    sort_order: Optional[SortOrder] = SortOrder.DESC,
    limit: Optional[int] = 100,
    offset: Optional[int] = 0,
    resolve_span: bool = False,
    combine_columns: bool = False,
    include_deleted: bool = False,
    exclude_signals: bool = False,
    user: Optional[UserInfo] = None,
  ) -> SelectRowsResult:
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
      resolve_span: Whether to resolve the span of the row.
      combine_columns: Whether to combine columns into a single object. The object will be pruned
        to only include sub-fields that correspond to the requested columns.
      include_deleted: Whether to include deleted rows in the query.
      exclude_signals: Whether to exclude fields produced by signals.
      user: The authenticated user, if auth is enabled and the user is logged in. This is used to
        apply ACL to the query, especially for concepts.

    Returns:
      A `SelectRowsResult` iterator with rows of `Item`s.
    """
    pass

  @abc.abstractmethod
  def select_rows_schema(
    self,
    columns: Optional[Sequence[ColumnId]] = None,
    sort_by: Optional[Sequence[Path]] = None,
    sort_order: Optional[SortOrder] = SortOrder.DESC,
    searches: Optional[Sequence[Search]] = None,
    combine_columns: bool = False,
  ) -> SelectRowsSchemaResult:
    """Returns the schema of the result of `select_rows` above with the same arguments."""
    pass

  @abc.abstractmethod
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
    """Adds a label to a row, or a set of rows defined by searches and filters.

    Returns the number of added labels.
    """
    pass

  @abc.abstractmethod
  def get_embeddings(self, embedding: str, rowid: str, path: Union[PathKey, str]) -> list[Item]:
    """Returns the span-level embeddings associated with a specific row value.

    Args:
      embedding: The embedding name (e.g. `gte-small`, or `jina-v2-small`).
      rowid: The row id to get embeddings for.
      path: The path within a row to get embeddings for.
        - If the row is a struct, e.g. {person: {document: {text: ...}}} and we want the embeddings
        for text, the row path would be `person.document.text`.
        - If the row has a list of strings, e.g. {docs: [{text: ...}, {text: ...}]}, then the
          row path would be `docs.0.text` for the 1st doc and `docs.1.text` for the 2nd doc.

    Returns:
      A list of `ll.Item` dicts holding the span coordinates and the embedding. These come from
      ll.chunk_embedding, which looks like:
      ```
      {'__span__': {'start': 0, 'end': 6}, 'embedding': array([1., 0., 0.])}
      ```
    """
    pass

  @abc.abstractmethod
  def get_label_names(self) -> list[str]:
    """Returns the list of label names that have been added to the dataset."""
    pass

  @abc.abstractmethod
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
    """Removes labels from a row, or a set of rows defined by searches and filters.

    Returns the number of removed labels.
    """
    pass

  def delete_rows(
    self,
    row_ids: Optional[Sequence[str]] = None,
    searches: Optional[Sequence[Search]] = None,
    filters: Optional[Sequence[FilterLike]] = None,
    sort_by: Optional[Sequence[Path]] = None,
    sort_order: Optional[SortOrder] = SortOrder.DESC,
    limit: Optional[int] = None,
    offset: Optional[int] = 0,
  ) -> int:
    """Deletes rows from the dataset.

    Returns the number of deleted rows.
    """
    return self.add_labels(
      name=DELETED_LABEL_NAME,
      row_ids=row_ids,
      searches=searches,
      filters=filters,
      sort_by=sort_by,
      sort_order=sort_order,
      limit=limit,
      offset=offset,
    )

  def restore_rows(
    self,
    row_ids: Optional[Sequence[str]] = None,
    searches: Optional[Sequence[Search]] = None,
    filters: Optional[Sequence[FilterLike]] = None,
    sort_by: Optional[Sequence[Path]] = None,
    sort_order: Optional[SortOrder] = SortOrder.DESC,
    limit: Optional[int] = None,
    offset: Optional[int] = 0,
  ) -> int:
    """Undeletes rows from the dataset.

    Returns the number of restored rows.
    """
    return self.remove_labels(
      DELETED_LABEL_NAME,
      row_ids=row_ids,
      searches=searches,
      filters=filters,
      sort_by=sort_by,
      sort_order=sort_order,
      limit=limit,
      offset=offset,
      include_deleted=True,
    )

  @abc.abstractmethod
  def stats(self, leaf_path: Path, include_deleted: bool = False) -> StatsResult:
    """Compute stats for a leaf path.

    Args:
      leaf_path: The leaf path to compute stats for.
      include_deleted: Whether to include deleted rows in the stats.

    Returns:
      A StatsResult.
    """
    pass

  @abc.abstractmethod
  def media(self, item_id: str, leaf_path: Path) -> MediaResult:
    """Return the media for a leaf path.

    Args:
      item_id: The item id to get media for.
      leaf_path: The leaf path for the media.

    Returns:
      A MediaResult.
    """
    pass

  @abc.abstractmethod
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
  ) -> Iterable[Item]:
    """Maps a function over all rows in the dataset and writes the result to a new column.

    Args:
      map_fn: A callable that takes a full row item dictionary, and returns an Item for the
        result. The result Item can be a primitive, like a string.
      input_path: The path to the input column to map over. If not specified, the map function will
        be called with the full row item dictionary. If specified, the map function will be called
        with the value at the given path, flattened. The output column will be written in the same
        shape as the input column, paralleling its nestedness.
      output_path: The name of the output path to write to. It is often useful to emit results
        next to the input, so they will get hierarchically shown in the UI.
      overwrite: Set to true to overwrite this column if it already exists. If this bit is False,
        an error will be thrown if the column already exists.
      resolve_span: Whether to resolve the spans into text before calling the map function.
      batch_size: If provided, the map function will be called with a list of rows. Useful for
        batching API requests or other expensive operations. If unspecified, the map will receive
        one item at a time.
      filters: Filters limiting the set of rows to map over. At the moment, we do not support
        incremental computations; the output column will be null for rows that do not match the
        filter, and there is no way to fill in those nulls without recomputing the entire map with
        a less restrictive filter and overwrite=True.
      limit: How many rows to map over. If not specified, all rows will be mapped over.
      sort_by: The path to sort by. If specified, the map will be called with rows sorted by this
        path. This is useful for map functions that need to maintain state across rows.
      sort_order: The sort order. Defaults to ascending.
      include_deleted: Whether to include deleted rows in the query.
      num_jobs: The number of jobs to shard the work, defaults to 1. When set to -1, the number of
        jobs will correspond to the number of processors. If `num_jobs` is greater than the number
        of processors, it split the work into `num_jobs` and distribute amongst processors.
      execution_type: The local execution type of the map. Either "threads" or "processes". Threads
        are better for network bound tasks like making requests to an external server, while
        processes are better for CPU bound tasks, like running a local LLM.
      embedding: If specified, the map function will be called with the `lilac.SpanVector`s
        of each item, instead of the original text. This is needed for embedding-based computations
        (e.g. clustering).
      schema: The schema for the output of the map function. If not provided, the schema will be
        auto inferred.

    Returns:
      An iterable of items that are the result of map. The result item does not have the column name
      as part of the dictionary, it is exactly what is returned from the map.
    """
    pass

  def transform(
    self,
    transform_fn: Callable[[Iterator[Item]], Iterator[Item]],
    input_path: Optional[Path] = None,
    output_path: Optional[Path] = None,
    overwrite: bool = False,
    resolve_span: bool = False,
    filters: Optional[Sequence[FilterLike]] = None,
    limit: Optional[int] = None,
    sort_by: Optional[Path] = None,
    sort_order: Optional[SortOrder] = SortOrder.ASC,
    embedding: Optional[str] = None,
    schema: Optional[Field] = None,
  ) -> Iterable[Item]:
    """Transforms the entire dataset (or a column) and writes the result to a new column.

    Args:
      transform_fn: A callable that takes an iterable of all items in the dataset, and returns an
      iterable of the same length for the result.
      input_path: The path to the input column to map over. If not specified, the map function will
        be called with the full row item dictionary. If specified, the map function will be called
        with the value at the given path, flattened. The output column will be written in the same
        shape as the input column, paralleling its nestedness.
      output_path: The name of the output path to write to. It is often useful to emit results
        next to the input, so they will get hierarchically shown in the UI.
      overwrite: Set to true to overwrite this column if it already exists. If this bit is False,
        an error will be thrown if the column already exists.
      resolve_span: Whether to resolve the spans into text before calling the map function.
      filters: Filters limiting the set of rows to map over. At the moment, we do not support
        incremental computations; the output column will be null for rows that do not match the
        filter, and there is no way to fill in those nulls without recomputing the entire map with
        a less restrictive filter and overwrite=True.
      limit: How many rows to map over. If not specified, all rows will be mapped over.
      sort_by: The path to sort by. If specified, the map will be called with rows sorted by this
        path. This is useful for map functions that need to maintain state across rows.
      sort_order: The sort order. Defaults to ascending.
      embedding: If specified, the transform function will be called with the `lilac.SpanVector`s
        of each item, instead of the original text. This is needed for embedding-based computations
        (e.g. clustering).
      schema: The schema for the output of the map function. If not provided, the schema will be
        auto inferred.
    """
    return self.map(
      map_fn=transform_fn,
      input_path=input_path,
      output_path=output_path,
      overwrite=overwrite,
      resolve_span=resolve_span,
      batch_size=-1,
      filters=filters,
      limit=limit,
      sort_by=sort_by,
      sort_order=sort_order,
      num_jobs=1,
      execution_type='threads',
      embedding=embedding,
      schema=schema,
    )

  @abc.abstractmethod
  def to_huggingface(
    self,
    columns: Optional[Sequence[ColumnId]] = None,
    filters: Optional[Sequence[FilterLike]] = None,
    include_labels: Optional[Sequence[str]] = None,
    exclude_labels: Optional[Sequence[str]] = None,
    include_deleted: bool = False,
    include_signals: bool = False,
  ) -> HuggingFaceDataset:
    """Export the dataset to a huggingface dataset.

    Args:
      columns: The columns to export.
      filters: The filters to apply to the query.
      include_labels: The labels to include in the export.
      exclude_labels: The labels to exclude in the export.
      include_deleted: Whether to include deleted rows in the export.
      include_signals: Whether to include fields produced by signals.
    """
    pass

  @abc.abstractmethod
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
    """Export the dataset to a JSON file.

    Args:
      filepath: The path to the file to export to.
      jsonl: Whether to export to JSONL or JSON.
      columns: The columns to export.
      filters: The filters to apply to the query.
      include_labels: The labels to include in the export.
      exclude_labels: The labels to exclude in the export.
      include_deleted: Whether to include deleted rows in the export.
      include_signals: Whether to include fields produced by signals.
    """
    pass

  @abc.abstractmethod
  def to_pandas(
    self,
    columns: Optional[Sequence[ColumnId]] = None,
    filters: Optional[Sequence[FilterLike]] = None,
    include_labels: Optional[Sequence[str]] = None,
    exclude_labels: Optional[Sequence[str]] = None,
    include_deleted: bool = False,
    include_signals: bool = False,
  ) -> pd.DataFrame:
    """Export the dataset to a pandas DataFrame.

    Args:
      columns: The columns to export.
      filters: The filters to apply to the query.
      include_labels: The labels to include in the export.
      exclude_labels: The labels to exclude in the export.
      include_deleted: Whether to include deleted rows in the export.
      include_signals: Whether to include fields produced by signals.
    """
    pass

  @abc.abstractmethod
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
    """Export the dataset to a parquet file.

    Args:
      filepath: The path to the file to export to.
      columns: The columns to export.
      filters: The filters to apply to the query.
      include_labels: The labels to include in the export.
      exclude_labels: The labels to exclude in the export.
      include_deleted: Whether to include deleted rows in the export.
      include_signals: Whether to include fields produced by signals.
    """
    pass

  @abc.abstractmethod
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
    """Export the dataset to a csv file.

    Args:
      filepath: The path to the file to export to.
      columns: The columns to export.
      filters: The filters to apply to the query.
      include_labels: The labels to include in the export.
      exclude_labels: The labels to exclude in the export.
      include_deleted: Whether to include deleted rows in the export.
      include_signals: Whether to include fields produced by signals.
    """
    pass

  def petals(self) -> dict[PathTuple, Field]:
    """Return the leafs of the dataset."""
    return self.manifest().data_schema.leafs


def default_settings(dataset: Dataset) -> DatasetSettings:
  """Gets the default settings for a dataset."""
  schema = dataset.manifest().data_schema
  leaf_paths = [
    path for path, field in schema.leafs.items() if field.dtype == STRING and path != (ROWID,)
  ]
  pool = ThreadPoolExecutor()
  stats: list[StatsResult] = list(pool.map(lambda leaf: dataset.stats(leaf), leaf_paths))
  media_paths: list[PathTuple] = [
    s.path for s in stats if s.avg_text_length and s.avg_text_length >= MEDIA_AVG_TEXT_LEN
  ]
  if not media_paths:
    # If there are no long text fields, pick the longest of the short text field.
    sorted_stats = sorted(
      [s for s in stats if s.avg_text_length], key=lambda s: s.avg_text_length or -1.0, reverse=True
    )
    if sorted_stats:
      media_paths = [sorted_stats[0].path]

  return DatasetSettings(ui=DatasetUISettings(media_paths=media_paths))


def config_from_dataset(dataset: Dataset) -> DatasetConfig:
  """Computes a DatasetConfig from a manifest.

  NOTE: This is only used for backwards compatibility. Once we remove the back-compat logic, this
  method can be removed.
  """
  manifest = dataset.manifest()
  all_fields = manifest.data_schema.all_fields

  all_signals = [
    (path, resolve_signal(field.signal)) for (path, field) in all_fields if field.signal
  ]
  signals: list[tuple[PathTuple, Signal]] = []
  embeddings: list[tuple[PathTuple, TextEmbeddingSignal]] = []
  for path, s in all_signals:
    source_path = path[0:-1]  # Remove the signal name from the path.
    if isinstance(s, TextEmbeddingSignal):
      embeddings.append((source_path, s))
    else:
      signals.append((source_path, s))

  return DatasetConfig(
    namespace=manifest.namespace,
    name=manifest.dataset_name,
    source=manifest.source,
    signals=[SignalConfig(path=path, signal=signal) for path, signal in signals],
    embeddings=[
      EmbeddingConfig(path=path, embedding=embedding.name) for path, embedding in embeddings
    ],
    settings=default_settings(dataset),
  )


def make_signal_parquet_id(
  signal: Signal, source_path: PathTuple, is_computed_signal: Optional[bool] = False
) -> str:
  """Return a unique identifier for this parquet table."""
  # Remove the wildcards from the parquet id since they are implicit.
  path = [*[p for p in source_path if p != PATH_WILDCARD], signal.key(is_computed_signal)]
  return '.'.join(path)


def get_map_parquet_id(output_path: PathTuple) -> str:
  """Return a unique identifier for this parquet table."""
  # Remove the wildcards from the parquet id since they are implicit.
  return 'map.' + '.'.join(output_path)
