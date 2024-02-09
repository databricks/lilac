"""Clustering utilities."""
import gc
import itertools
from typing import Callable, Iterator, Optional, Union, cast

import modal
import numpy as np
from tqdm import tqdm

from ..batch_utils import compress_docs, flatten_path_iter
from ..dataset_format import DatasetFormatInputSelector
from ..embeddings.jina import JinaV2Small
from ..schema import (
  EMBEDDING_KEY,
  PATH_WILDCARD,
  VALUE_KEY,
  ClusterInfo,
  ClusterInputFormatSelectorInfo,
  Item,
  Path,
  PathTuple,
  field,
  normalize_path,
)
from ..signal import (
  TopicFn,
)
from ..tasks import TaskId, TaskInfo, get_task_manager
from ..utils import DebugTimer, chunks, log
from .cluster_titling import (
  compute_titles,
  generate_category_openai,
  generate_title_openai,
)
from .dataset import Dataset
from .dataset_utils import (
  get_callable_name,
  sparse_to_dense_compute,
)

CLUSTER_ID = 'cluster_id'
CLUSTER_MEMBERSHIP_PROB = 'cluster_membership_prob'
CLUSTER_TITLE = 'cluster_title'

CATEGORY_ID = 'category_id'
CATEGORY_MEMBERSHIP_PROB = 'category_membership_prob'
CATEGORY_TITLE = 'category_title'

FIELD_SUFFIX = 'cluster'

MIN_CLUSTER_SIZE = 10
MIN_CLUSTER_SIZE_CATEGORY = 5
UMAP_DIM = 5
UMAP_SEED = 42
HDBSCAN_SELECTION_EPS = 0.05
BATCH_SOFT_CLUSTER_NOISE = 1024


def cluster_impl(
  dataset: Dataset,
  input_fn_or_path: Union[Path, Callable[[Item], str], DatasetFormatInputSelector],
  output_path: Optional[Path] = None,
  min_cluster_size: int = MIN_CLUSTER_SIZE,
  topic_fn: Optional[TopicFn] = None,
  category_fn: Optional[TopicFn] = None,
  overwrite: bool = False,
  use_garden: bool = False,
  task_id: Optional[TaskId] = None,
  recompute_titles: bool = False,
  batch_size_titling: Optional[int] = None,
) -> None:
  """Compute clusters for a field of the dataset."""
  topic_fn = topic_fn or generate_title_openai
  category_fn = category_fn or generate_category_openai
  task_manager = get_task_manager()
  task_info: Optional[TaskInfo] = None
  if task_id:
    task_info = task_manager.get_task_info(task_id)
  manifest = dataset.manifest()
  schema = manifest.data_schema
  path: Optional[PathTuple] = None

  dataset_format_input_selector: Optional[DatasetFormatInputSelector] = None
  if isinstance(input_fn_or_path, DatasetFormatInputSelector):
    dataset_format_input_selector = input_fn_or_path
    input_fn_or_path = input_fn_or_path.selector

  if not callable(input_fn_or_path):
    path = normalize_path(input_fn_or_path)
    # Make sure the path exists.
    if not schema.has_field(path):
      raise ValueError(f'Path {path} does not exist in the dataset.')
    input_field = schema.get_field(path)
    if not input_field.dtype or input_field.dtype.type != 'string':
      raise ValueError(f'Path {path} must be a string field.')

  elif not output_path:
    raise ValueError(
      '`output_path` must be provided to `Dataset.cluster()` when `input` is a user-provided '
      'method.'
    )

  # Output the cluster enrichment to a sibling path, unless an output path is provided by the user.
  if output_path:
    cluster_output_path = normalize_path(output_path)
  elif path:
    # The sibling output path is the same as the input path, but with a different suffix.
    index = 0
    for i, path_part in enumerate(path):
      if path_part == PATH_WILDCARD:
        break
      else:
        index = i

    parent = path[:index]
    sibling = '_'.join([p for p in path[index:] if p != PATH_WILDCARD])
    cluster_output_path = (*parent, f'{sibling}__{FIELD_SUFFIX}')
  else:
    raise ValueError('input must be provided.')

  # Extract the text from the input path into a temporary column.
  TEXT_COLUMN = 'text'
  temp_text_path = (*cluster_output_path, TEXT_COLUMN)
  temp_path_exists = schema.has_field(temp_text_path)
  if not temp_path_exists or overwrite:
    # Since input is a function, map over the dataset to make a temporary column with that text.
    if task_info:
      task_info.message = 'Extracting text from items'

    def _flatten_input(item: Item, input_path: PathTuple) -> str:
      texts = flatten_path_iter(item, input_path)
      # Filter out Nones
      texts = (t for t in texts if t)
      # Deal with enriched items.
      texts = (t[VALUE_KEY] if (isinstance(t, dict) and VALUE_KEY in t) else t for t in texts)
      return '\n'.join(texts)

    def extract_text(item: Item) -> Item:
      cluster_item = item
      for path_part in cluster_output_path:
        cluster_item = cluster_item.get(path_part, {})

      text = (
        input_fn_or_path(item)
        if callable(input_fn_or_path)
        else _flatten_input(item, cast(PathTuple, path))
      )
      return {**cluster_item, TEXT_COLUMN: text}

    dataset.map(extract_text, output_path=cluster_output_path, overwrite=True)

  total_len = dataset.stats(temp_text_path).total_count

  cluster_ids_exists = schema.has_field((*cluster_output_path, CLUSTER_ID))
  if not cluster_ids_exists or overwrite:
    if task_info:
      task_info.message = 'Clustering documents'
      task_info.total_progress = 0
      task_info.total_len = None

    def cluster_documents(items: Iterator[Item]) -> Iterator[Item]:
      items, items2 = itertools.tee(items)
      docs: Iterator[Optional[str]] = (item.get(TEXT_COLUMN) for item in items)
      cluster_items = sparse_to_dense_compute(
        docs,
        lambda x: _hdbscan_cluster(
          x, min_cluster_size, use_garden, num_docs=total_len, task_info=task_info
        ),
      )
      for item, cluster_item in zip(items2, cluster_items):
        yield {**item, **(cluster_item or {})}

    # Compute the clusters.
    dataset.transform(
      cluster_documents,
      input_path=cluster_output_path,
      output_path=cluster_output_path,
      overwrite=True,
    )

  cluster_titles_exist = schema.has_field((*cluster_output_path, CLUSTER_TITLE))
  if not cluster_titles_exist or overwrite or recompute_titles:
    if task_info:
      task_info.message = 'Titling clusters'
      task_info.total_progress = 0
      task_info.total_len = total_len

    def title_clusters(items: Iterator[Item]) -> Iterator[Item]:
      items, items2 = itertools.tee(items)
      titles = compute_titles(
        items,
        text_column=TEXT_COLUMN,
        cluster_id_column=CLUSTER_ID,
        membership_column=CLUSTER_MEMBERSHIP_PROB,
        topic_fn=topic_fn,
        batch_size=batch_size_titling,
        task_info=task_info,
      )
      for item, title in zip(items2, titles):
        yield {**item, CLUSTER_TITLE: title}

    dataset.transform(
      title_clusters,
      input_path=cluster_output_path,
      output_path=cluster_output_path,
      sort_by=(*cluster_output_path, CLUSTER_ID),
      overwrite=True,
    )

  category_id_exists = schema.has_field((*cluster_output_path, CATEGORY_ID))
  if not category_id_exists or overwrite or recompute_titles:
    if task_info:
      task_info.message = 'Clustering titles'
      task_info.total_progress = 0
      task_info.total_len = None

    def cluster_titles(items: Iterator[Item]) -> Iterator[Item]:
      items, items2 = itertools.tee(items)
      docs = (item.get(CLUSTER_TITLE) for item in items)
      cluster_items = sparse_to_dense_compute(
        docs, lambda x: _hdbscan_cluster(x, MIN_CLUSTER_SIZE_CATEGORY, use_garden)
      )
      for item, cluster_item in zip(items2, cluster_items):
        item[CATEGORY_ID] = (cluster_item or {}).get(CLUSTER_ID, -1)
        item[CATEGORY_MEMBERSHIP_PROB] = (cluster_item or {}).get(CLUSTER_MEMBERSHIP_PROB, 0)
        yield item

    # Compute the clusters.
    dataset.transform(
      cluster_titles,
      input_path=cluster_output_path,
      output_path=cluster_output_path,
      overwrite=True,
    )

  category_title_path = (*cluster_output_path, CATEGORY_TITLE)
  category_title_exists = schema.has_field(category_title_path)
  if not category_title_exists or overwrite or recompute_titles:
    if task_info:
      task_info.message = 'Titling categories'
      task_info.total_progress = 0
      task_info.total_len = total_len

    def title_categories(items: Iterator[Item]) -> Iterator[Item]:
      items, items2 = itertools.tee(items)
      titles = compute_titles(
        items,
        text_column=CLUSTER_TITLE,
        cluster_id_column=CATEGORY_ID,
        membership_column=CATEGORY_MEMBERSHIP_PROB,
        topic_fn=category_fn,
        batch_size=batch_size_titling,
        task_info=task_info,
      )
      for item, title in zip(items2, titles):
        # Drop the temporary newline-concatenated text column.
        if TEXT_COLUMN in item:
          del item[TEXT_COLUMN]
        yield {**item, CATEGORY_TITLE: title}

    dataset.transform(
      title_categories,
      input_path=cluster_output_path,
      output_path=cluster_output_path,
      sort_by=(*cluster_output_path, CATEGORY_ID),
      overwrite=True,
    )

  def drop_temp_text_column(items: Iterator[Item]) -> Iterator[Item]:
    for item in items:
      if TEXT_COLUMN in item:
        del item[TEXT_COLUMN]
      yield item

  # Drop the temporary newline-concatenated text column and write the final output.
  dataset.transform(
    drop_temp_text_column,
    input_path=cluster_output_path,
    output_path=cluster_output_path,
    overwrite=True,
    schema=field(
      fields={
        CLUSTER_ID: field('int32', categorical=True),
        CLUSTER_MEMBERSHIP_PROB: 'float32',
        CLUSTER_TITLE: 'string',
        CATEGORY_ID: field('int32', categorical=True),
        CATEGORY_MEMBERSHIP_PROB: 'float32',
        CATEGORY_TITLE: 'string',
      },
      cluster=ClusterInfo(
        min_cluster_size=min_cluster_size,
        use_garden=use_garden,
        input_path=(get_callable_name(input_fn_or_path),) if callable(input_fn_or_path) else path,
        input_format_selector=ClusterInputFormatSelectorInfo(
          format=manifest.dataset_format.name,
          selector=dataset_format_input_selector.name,
        )
        if dataset_format_input_selector and manifest.dataset_format
        else None,
      ),
    ),
  )


def _hdbscan_cluster(
  docs: Iterator[str],
  min_cluster_size: int,
  use_garden: bool = False,
  num_docs: Optional[int] = None,
  task_info: Optional[TaskInfo] = None,
) -> Iterator[Item]:
  """Cluster docs with HDBSCAN."""
  if use_garden:
    remote_fn = modal.Function.lookup('cluster', 'Cluster.cluster').remote
    with DebugTimer('Compressing docs for clustering remotely'):
      gzipped_docs = compress_docs(list(docs))
    response = remote_fn({'gzipped_docs': gzipped_docs, 'min_cluster_size': min_cluster_size})
    yield from response['clusters']

  if task_info:
    task_info.message = 'Computing embeddings'
    task_info.total_progress = 0
    task_info.total_len = num_docs
  with DebugTimer('Computing embeddings'):
    jina = JinaV2Small()
    jina.setup()
    response = []
    for doc in tqdm(docs, position=0, desc='Computing embeddings', total=num_docs):
      response.extend(jina.compute([doc]))
      if task_info and task_info.total_progress is not None:
        task_info.total_progress += 1
    jina.teardown()

  del docs, jina
  all_vectors = np.array([r[0][EMBEDDING_KEY] for r in response], dtype=np.float32)
  del response
  gc.collect()

  # Use UMAP to reduce the dimensionality before hdbscan to speed up clustering.
  # For details on hyperparameters, see:
  # https://umap-learn.readthedocs.io/en/latest/clustering.html

  # Try to import the cuml version of UMAP, which is much faster than the sklearn version.
  # if CUDA is available.
  try:
    from cuml import UMAP  # type: ignore
  except ImportError:
    from umap import UMAP

  dim = all_vectors[0].size
  with DebugTimer(f'UMAP: Reducing dim from {dim} to {UMAP_DIM} of {len(all_vectors)} vectors'):
    n_neighbors = min(30, len(all_vectors) - 1)
    if UMAP_DIM < dim and UMAP_DIM < len(all_vectors):
      reducer = UMAP(
        n_components=UMAP_DIM,
        n_neighbors=n_neighbors,
        min_dist=0.0,
        n_jobs=-1,
        random_state=UMAP_SEED,
      )
      all_vectors = reducer.fit_transform(all_vectors)

  gc.collect()

  # Try to import the cuml version of HDBSCAN, which is much faster than the sklearn version.
  # if CUDA is available.
  try:
    from cuml.cluster.hdbscan import HDBSCAN, membership_vector  # type: ignore
  except ImportError:
    from hdbscan import HDBSCAN, membership_vector

  with DebugTimer('HDBSCAN: Clustering'):
    min_cluster_size = min(min_cluster_size, len(all_vectors))
    clusterer = HDBSCAN(
      min_cluster_size=min_cluster_size,
      min_samples=min_cluster_size - 1,
      cluster_selection_epsilon=HDBSCAN_SELECTION_EPS,
      cluster_selection_method='leaf',
      prediction_data=True,
    )
    clusterer.fit(all_vectors)

  noisy_vectors: list[np.ndarray] = []
  for i, cluster_id in enumerate(clusterer.labels_):
    if cluster_id == -1:
      noisy_vectors.append(all_vectors[i])
  num_noisy = len(noisy_vectors)
  perc_noisy = 100 * num_noisy / len(clusterer.labels_)
  log(f'{num_noisy} noise points ({perc_noisy:.1f}%) will be assigned to nearest cluster.')

  noisy_labels: list[np.ndarray] = []
  noisy_probs: list[np.ndarray] = []
  labels = clusterer.labels_
  memberships = clusterer.probabilities_
  if num_noisy > 0 and num_noisy < len(clusterer.labels_):
    with DebugTimer('HDBSCAN: Computing membership for the noise points'):
      for batch_noisy_vectors in chunks(noisy_vectors, BATCH_SOFT_CLUSTER_NOISE):
        batch_noisy_vectors = np.array(batch_noisy_vectors, dtype=np.float32)
        soft_clusters = membership_vector(clusterer, batch_noisy_vectors)
        if soft_clusters.ndim < 2:
          soft_clusters = soft_clusters.reshape(-1, 1)
        noisy_labels.append(np.argmax(soft_clusters, axis=1))
        noisy_probs.append(np.max(soft_clusters, axis=1))

    noisy_labels = np.concatenate(noisy_labels, axis=0, dtype=np.int32)
    noisy_probs = np.concatenate(noisy_probs, axis=0, dtype=np.float32)
    noise_index = 0
    for i, cluster_id in enumerate(labels):
      if cluster_id == -1:
        labels[i] = noisy_labels[noise_index]
        memberships[i] = noisy_probs[noise_index]
        noise_index += 1

  del clusterer, all_vectors, noisy_vectors
  gc.collect()

  for cluster_id, membership_prob in zip(labels, memberships):
    yield {CLUSTER_ID: int(cluster_id), CLUSTER_MEMBERSHIP_PROB: float(membership_prob)}
