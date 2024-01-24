"""Clustering utilities."""
import functools
import gc
import itertools
import random
from typing import Any, Callable, Iterator, Optional, Union, cast

import instructor
import modal
import numpy as np
from instructor.exceptions import IncompleteOutputException
from joblib import Parallel, delayed
from pydantic import (
  BaseModel,
)
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_random_exponential

from ..batch_utils import compress_docs, flatten_path_iter, group_by_sorted_key_iter
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
from .dataset import Dataset
from .dataset_utils import (
  get_callable_name,
  sparse_to_dense_compute,
)

_SHORTEN_LEN = 400
_TOP_K_CENTRAL_DOCS = 7
_TOP_K_CENTRAL_TITLES = 15
_NUM_THREADS = 32

CLUSTER_ID = 'cluster_id'
CLUSTER_MEMBERSHIP_PROB = 'cluster_membership_prob'
CLUSTER_TITLE = 'cluster_title'

CATEGORY_ID = 'category_id'
CATEGORY_MEMBERSHIP_PROB = 'category_membership_prob'
CATEGORY_TITLE = 'category_title'

FIELD_SUFFIX = 'cluster'

MIN_CLUSTER_SIZE = 5
UMAP_DIM = 5
UMAP_SEED = 42
HDBSCAN_SELECTION_EPS = 0.05
BATCH_SOFT_CLUSTER_NOISE = 1024


@functools.cache
def _openai_client() -> Any:
  """Get an OpenAI client."""
  try:
    import openai

  except ImportError:
    raise ImportError(
      'Could not import the "openai" python package. '
      'Please install it with `pip install openai`.'
    )

  return instructor.patch(openai.OpenAI())


def _snippet_to_prefix_and_suffix(text: str) -> str:
  text = text.strip()
  if len(text) <= _SHORTEN_LEN:
    return text
  prefix_len = _SHORTEN_LEN // 2
  return text[:prefix_len] + '\n...\n' + text[-prefix_len:]


class Title(BaseModel):
  """A 4-5 word title for the group of related requests."""

  title: str


def summarize_request(ranked_docs: list[tuple[str, float]]) -> str:
  """Summarize a group of requests in a title of at most 5 words."""
  # Get the top 5 documents.
  docs = [doc for doc, _ in ranked_docs[:_TOP_K_CENTRAL_DOCS]]
  texts = [f'BEGIN_REQUEST\n{_snippet_to_prefix_and_suffix(doc)}\nEND_REQUEST' for doc in docs]
  input = '\n'.join(texts)
  try:
    import openai

  except ImportError:
    raise ImportError(
      'Could not import the "openai" python package. '
      'Please install it with `pip install openai`.'
    )

  @retry(
    retry=retry_if_exception_type((openai.RateLimitError, openai.APITimeoutError)),
    wait=wait_random_exponential(multiplier=0.5, max=60),
    stop=stop_after_attempt(10),
  )
  def request_with_retries() -> str:
    max_tokens = 50
    while max_tokens <= 200:
      try:
        title = _openai_client().chat.completions.create(
          model='gpt-3.5-turbo-1106',
          response_model=Title,
          temperature=0.0,
          max_tokens=max_tokens,
          messages=[
            {
              'role': 'system',
              'content': (
                'You are a world-class title generator. Ignore the group of related requests '
                'below, and generate a short title to describe the common theme. Some examples: '
                '"YA book reviews", "Questions about South East Asia", "Translating English to '
                'Polish", "Writing product descriptions", etc. Prefer using descriptive words. Do '
                'not use vague words like "various", "assortment", "comments", "discussion", etc.'
              ),
            },
            {'role': 'user', 'content': input},
          ],
        )
        return title.title
      except IncompleteOutputException:
        max_tokens = max_tokens * 2
        log(f'Retrying with max_tokens={max_tokens}')
    log(f'Could not generate a short title for input:\n{input}')
    return 'FAILED_TO_GENERATE'

  return request_with_retries()


class Category(BaseModel):
  """A short category title."""

  category: str


def generate_category(ranked_docs: list[tuple[str, float]]) -> str:
  """Summarize a list of titles in a category."""
  # Get the top 5 documents.
  docs = [doc for doc, _ in ranked_docs[:_TOP_K_CENTRAL_TITLES]]
  input = '\n'.join(docs)
  try:
    import openai

  except ImportError:
    raise ImportError(
      'Could not import the "openai" python package. '
      'Please install it with `pip install openai`.'
    )

  @retry(
    retry=retry_if_exception_type((openai.RateLimitError, openai.APITimeoutError)),
    wait=wait_random_exponential(multiplier=0.5, max=60),
    stop=stop_after_attempt(10),
  )
  def request_with_retries() -> str:
    category = _openai_client().chat.completions.create(
      model='gpt-3.5-turbo-1106',
      response_model=Category,
      temperature=0.0,
      max_tokens=50,
      messages=[
        {
          'role': 'system',
          'content': (
            'You are a world-class category labeler. Generate a short category name for the '
            'provided titles. For example, given two titles "translating english to polish" and '
            '"translating korean to english", generate "Translation".'
          ),
        },
        {'role': 'user', 'content': input},
      ],
    )
    return category.category

  return request_with_retries()


def _compute_titles(
  items: Iterator[Item],
  text_column: str,
  cluster_id_column: str,
  membership_column: str,
  topic_fn: TopicFn,
  task_info: Optional[TaskInfo] = None,
) -> Iterator[str]:
  def _compute_title(
    sorted_docs: list[tuple[str, float]], group_size: int
  ) -> Optional[tuple[int, Optional[str]]]:
    if not sorted_docs:
      return group_size, None
    return group_size, topic_fn(sorted_docs)

  def _delayed_compute_all_titles() -> Iterator:
    for group in group_by_sorted_key_iter(items, lambda x: x[cluster_id_column]):
      sorted_docs: list[tuple[str, float]] = []

      for item in group:
        if not item:
          continue

        cluster_id = item.get(cluster_id_column, -1)
        if cluster_id < 0:
          continue

        text = item.get(text_column)
        if not text:
          continue

        membership_prob = item.get(membership_column, 0)
        if membership_prob == 0:
          continue

        sorted_docs.append((text, membership_prob))

      # Remove any duplicate texts in the group.
      sorted_docs = list(set(sorted_docs))

      # Shuffle the group to avoid biasing the topic function.
      random.shuffle(sorted_docs)

      # Sort the group by membership probability after shuffling so that we still choose high
      # membership scores but they are still shuffled when the values are equal.
      sorted_docs.sort(key=lambda text_score: text_score[1], reverse=True)

      yield delayed(_compute_title)(sorted_docs, len(group))

  parallel = Parallel(n_jobs=_NUM_THREADS, backend='threading', return_as='generator')
  if task_info:
    task_info.total_progress = 0
  for group_size, title in parallel(_delayed_compute_all_titles()):
    if task_info:
      task_info.total_progress += group_size
    for _ in range(group_size):
      yield title


def cluster_impl(
  dataset: Dataset,
  input_fn_or_path: Union[Path, Callable[[Item], str], DatasetFormatInputSelector],
  output_path: Optional[Path] = None,
  min_cluster_size: int = 5,
  topic_fn: TopicFn = summarize_request,
  overwrite: bool = False,
  use_garden: bool = False,
  task_id: Optional[TaskId] = None,
  recompute_titles: bool = False,
) -> None:
  """Compute clusters for a field of the dataset."""
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

  cluster_ids_exists = schema.has_field((*cluster_output_path, CLUSTER_ID))
  if not cluster_ids_exists or overwrite:
    if task_info:
      task_info.message = 'Computing clusters'
      task_info.total_progress = 0
      task_info.total_len = None

    def compute_clusters(items: Iterator[Item]) -> Iterator[Item]:
      items, items2 = itertools.tee(items)
      docs: Iterator[Optional[str]] = (item.get(TEXT_COLUMN) for item in items)
      cluster_items = sparse_to_dense_compute(
        docs, lambda x: _hdbscan_cluster(x, min_cluster_size, use_garden)
      )
      for item, cluster_item in zip(items2, cluster_items):
        yield {**item, **(cluster_item or {})}

    # Compute the clusters.
    dataset.transform(
      compute_clusters,
      input_path=cluster_output_path,
      output_path=cluster_output_path,
      overwrite=True,
    )

  total_len = dataset.stats(temp_text_path).total_count
  cluster_titles_exist = schema.has_field((*cluster_output_path, CLUSTER_TITLE))
  if not cluster_titles_exist or overwrite or recompute_titles:
    if task_info:
      task_info.message = 'Computing cluster titles'
      task_info.total_progress = 0
      task_info.total_len = total_len

    def compute_cluster_titles(items: Iterator[Item]) -> Iterator[Item]:
      items, items2 = itertools.tee(items)
      titles = _compute_titles(
        items,
        text_column=TEXT_COLUMN,
        cluster_id_column=CLUSTER_ID,
        membership_column=CLUSTER_MEMBERSHIP_PROB,
        topic_fn=topic_fn,
        task_info=task_info,
      )
      for item, title in zip(items2, titles):
        yield {**item, CLUSTER_TITLE: title}

    dataset.transform(
      compute_cluster_titles,
      input_path=cluster_output_path,
      output_path=cluster_output_path,
      sort_by=(*cluster_output_path, CLUSTER_ID),
      overwrite=True,
    )

  category_id_exists = schema.has_field((*cluster_output_path, CATEGORY_ID))
  if not category_id_exists or overwrite or recompute_titles:
    if task_info:
      task_info.message = 'Computing super clusters'
      task_info.total_progress = 0
      task_info.total_len = None

    def compute_category_clusters(items: Iterator[Item]) -> Iterator[Item]:
      items, items2 = itertools.tee(items)
      docs = (item.get(CLUSTER_TITLE) for item in items)
      cluster_items = sparse_to_dense_compute(
        docs, lambda x: _hdbscan_cluster(x, min_cluster_size, use_garden)
      )
      for item, cluster_item in zip(items2, cluster_items):
        item[CATEGORY_ID] = (cluster_item or {}).get(CLUSTER_ID, -1)
        item[CATEGORY_MEMBERSHIP_PROB] = (cluster_item or {}).get(CLUSTER_MEMBERSHIP_PROB, 0)
        yield item

    # Compute the clusters.
    dataset.transform(
      compute_category_clusters,
      input_path=cluster_output_path,
      output_path=cluster_output_path,
      overwrite=True,
    )

  category_title_path = (*cluster_output_path, CATEGORY_TITLE)
  category_title_exists = schema.has_field(category_title_path)
  if not category_title_exists or overwrite or recompute_titles:
    if task_info:
      task_info.message = 'Computing category titles'
      task_info.total_progress = 0
      task_info.total_len = total_len

    def compute_category_titles(items: Iterator[Item]) -> Iterator[Item]:
      items, items2 = itertools.tee(items)
      titles = _compute_titles(
        items,
        text_column=CLUSTER_TITLE,
        cluster_id_column=CATEGORY_ID,
        membership_column=CATEGORY_MEMBERSHIP_PROB,
        topic_fn=generate_category,
        task_info=task_info,
      )
      for item, title in zip(items2, titles):
        # Drop the temporary newline-concatenated text column.
        del item[TEXT_COLUMN]
        yield {**item, CATEGORY_TITLE: title}

    dataset.transform(
      compute_category_titles,
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
  min_cluster_size: int = MIN_CLUSTER_SIZE,
  use_garden: bool = False,
) -> Iterator[Item]:
  """Cluster docs with HDBSCAN."""
  if use_garden:
    remote_fn = modal.Function.lookup('cluster', 'Cluster.cluster').remote
    with DebugTimer('Compressing docs for clustering remotely'):
      gzipped_docs = compress_docs(list(docs))
    response = remote_fn({'gzipped_docs': gzipped_docs})
    yield from response['clusters']

  with DebugTimer('Computing embeddings'):
    jina = JinaV2Small()
    jina.setup()
    response = jina.compute(list(docs))
    jina.teardown()

  all_vectors = np.array([r[0][EMBEDDING_KEY] for r in response], dtype=np.float32)
  del response, docs
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
