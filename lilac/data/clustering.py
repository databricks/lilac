"""Clustering utilities."""
import functools
import gc
import random
import threading
from typing import Any, Callable, Iterator, Optional, Union, cast

import instructor
import modal
import numpy as np
from joblib import Parallel, delayed
from pydantic import (
  BaseModel,
)
from tenacity import retry, stop_after_attempt, wait_random_exponential

from ..batch_utils import compress_docs, flatten_path_iter
from ..embeddings.jina import JinaV2Small
from ..schema import (
  EMBEDDING_KEY,
  PATH_WILDCARD,
  VALUE_KEY,
  ClusterInfo,
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
from ..utils import DebugTimer
from .dataset import Dataset
from .dataset_utils import get_callable_name, get_common_ancestor, get_sibling_output_path

_SHORTEN_LEN = 400
_TOP_K_CENTRAL_DOCS = 7
_TOP_K_CENTRAL_TITLES = 15
_NUM_THREADS = 16

CLUSTER_ID = 'cluster_id'
CLUSTER_MEMBERSHIP_PROB = 'cluster_membership_prob'
CLUSTER_TITLE = 'cluster_title'

CATEROGY_ID = 'category_id'
CATEGORY_MEMBERSHIP_PROB = 'category_membership_prob'
CATEGORY_TITLE = 'category_title'

FIELD_SUFFIX = 'cluster'

MIN_CLUSTER_SIZE = 5
UMAP_DIM = 5
UMAP_SEED = 42


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
  """A 4-5 word title for the group of requests."""

  title: str


def summarize_request(ranked_docs: list[tuple[str, float]]) -> str:
  """Summarize a group of requests in a title of at most 5 words."""
  # Get the top 5 documents.
  docs = [doc for doc, _ in ranked_docs[:_TOP_K_CENTRAL_DOCS]]
  texts = [f'BEGIN_REQUEST\n{_snippet_to_prefix_and_suffix(doc)}\nEND_REQUEST' for doc in docs]
  input = '\n'.join(texts)
  title = _openai_client().chat.completions.create(
    model='gpt-3.5-turbo-1106',
    response_model=Title,
    temperature=0.0,
    top_p=0.1,
    max_tokens=50,
    messages=[
      {
        'role': 'system',
        'content': (
          'Ignore the group of requests below, and create a 4-5 word title to '
          'summarize the whole group. Some examples: "Classifying book review sentiment", '
          '"Questions about South East Asia", "Translating English to Polish", etc.'
        ),
      },
      {'role': 'user', 'content': input},
    ],
  )
  return title.title


class Category(BaseModel):
  """A short category title."""

  category: str


def _generate_category(ranked_docs: list[tuple[str, float]]) -> str:
  """Summarize a list of titles in a category."""
  # Get the top 5 documents.
  docs = [doc for doc, _ in ranked_docs[:_TOP_K_CENTRAL_TITLES]]
  input = '\n'.join(docs)
  category = _openai_client().chat.completions.create(
    model='gpt-3.5-turbo-1106',
    response_model=Category,
    temperature=0.0,
    top_p=0.1,
    max_tokens=50,
    messages=[
      {
        'role': 'system',
        'content': (
          'Create a short category name for the titles below. For example, for "translating '
          'english to polish" and "translating korean to english", output "Translation"'
        ),
      },
      {'role': 'user', 'content': input},
    ],
  )
  return category.category


def cluster(
  dataset: Dataset,
  input: Union[Path, Callable[[Item], str]],
  output_path: Optional[Path] = None,
  min_cluster_size: int = 5,
  topic_fn: TopicFn = summarize_request,
  overwrite: bool = False,
  remote: bool = False,
  category: bool = False,
  task_id: Optional[TaskId] = None,
) -> None:
  """Compute clusters for a field of the dataset."""
  task_manager = get_task_manager()
  task_info: Optional[TaskInfo] = None
  if task_id:
    task_info = task_manager.get_task_info(task_id)
  path: Optional[PathTuple] = None
  if not callable(input):
    path = normalize_path(input)
  elif not output_path:
    raise ValueError('output_path must be provided if input is a function.')

  schema = dataset.manifest().data_schema

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
  input_path = path
  path = (*cluster_output_path[:-1], '__temp_cluster_text__')
  temp_path_exists = schema.has_field(path)
  if not temp_path_exists or overwrite:
    # Since input is a function, map over the dataset to make a temporary column with that text.
    if task_info:
      task_info.message = 'Extracting text from items'

    def flatten_input(item: Item) -> str:
      texts = flatten_path_iter(item, cast(PathTuple, input_path))
      # Filter out Nones
      texts = (t for t in texts if t)
      # Deal with enriched items.
      texts = (t[VALUE_KEY] if VALUE_KEY in t else t for t in texts)
      return '\n'.join(texts)

    map_fn = input if callable(input) else flatten_input
    dataset.map(map_fn, output_path=path, overwrite=overwrite)

  clusters_exists = schema.has_field(cluster_output_path)
  if not clusters_exists or overwrite:
    if task_info:
      task_info.message = 'Computing super clusters' if category else 'Computing clusters'
      task_info.total_progress = 0
      task_info.total_len = None
    # Compute the clusters.
    dataset.transform(
      functools.partial(_cluster, min_cluster_size=min_cluster_size, remote=remote),
      input_path=path,
      output_path=cluster_output_path,
      # Providing schema to avoid inferring and to flag the cluster_id as categorical so the
      # histogram is sorted by size in the UI.
      schema=field(
        fields={CLUSTER_ID: field('int32', categorical=True), CLUSTER_MEMBERSHIP_PROB: 'float32'}
      ),
      overwrite=overwrite,
    )

  def _compute_titles(
    text_column: str, cluster_column: str, items: Iterator[Item]
  ) -> Iterator[Item]:
    # Group items by cluster id.
    groups: dict[int, list[tuple[str, float]]] = {}
    cluster_locks: dict[int, threading.Lock] = {}
    delayed_compute: list[Any] = []
    titles: dict[int, str] = {}

    @retry(wait=wait_random_exponential(multiplier=0.5, max=60), stop=stop_after_attempt(10))
    def _compute_title(cluster_id: int) -> Optional[str]:
      if cluster_id not in cluster_locks:
        return None
      with cluster_locks[cluster_id]:
        if cluster_id in titles:
          return titles[cluster_id]
        group = groups[cluster_id]
        if not group:
          return None
        topic = topic_fn(group)
        titles[cluster_id] = topic
        return topic

    for item in items:
      cluster_info = item[cluster_column]
      cluster_id: int
      if not cluster_info or CLUSTER_ID not in cluster_info:
        cluster_id = -1
      else:
        cluster_id = cluster_info[CLUSTER_ID]
      delayed_compute.append(delayed(_compute_title)(cluster_id))
      text = item[text_column]
      if not text:
        continue
      if not cluster_info:
        continue
      if cluster_id < 0 or cluster_id is None:
        continue
      membership_prob = cluster_info[CLUSTER_MEMBERSHIP_PROB] or 0
      if membership_prob == 0:
        continue
      cluster_locks.setdefault(cluster_id, threading.Lock())
      groups.setdefault(cluster_id, []).append((text, membership_prob))

    # Sort by descending membership score.
    for cluster_id, group in groups.items():
      # Remove any duplicate texts in the group.
      group = list(set(group))
      # Shuffle the group to avoid biasing the topic function.
      random.shuffle(group)
      group.sort(key=lambda text_score: text_score[1], reverse=True)
      groups[cluster_id] = group

    parallel = Parallel(n_jobs=_NUM_THREADS, backend='threading', return_as='generator')
    for i, item in enumerate(parallel(delayed_compute)):
      if task_info:
        task_info.total_progress = i
      yield item

  # Now that we have the clusters, compute the topic for each cluster with another transform.
  # The transform needs to be see both the original text and the cluster enrichment, so we need
  # to map over the ancestor path.
  ancestor_path, text_column, cluster_column = get_common_ancestor(path, cluster_output_path)

  # Output the title as a child of the cluster enrichment.
  title_output_path = (*cluster_output_path, CLUSTER_TITLE)

  titles_exist = schema.has_field(title_output_path)
  if not titles_exist or overwrite:
    if task_info:
      task_info.message = 'Computing category titles' if category else 'Computing titles'
      task_info.total_progress = 0
      task_info.total_len = dataset.stats(path).total_count

    dataset.transform(
      functools.partial(_compute_titles, text_column, cluster_column),
      input_path=ancestor_path,
      output_path=title_output_path,
      overwrite=overwrite,
      # Providing schema to avoid inferring.
      schema=field('string'),
    )

  # Delete the temporary text column.
  dataset.delete_column(path)

  if category:
    return

  # Cluster the titles into categories.
  category_cluster_output_path = get_sibling_output_path(title_output_path, FIELD_SUFFIX)
  cluster(
    dataset,
    title_output_path,
    output_path=category_cluster_output_path,
    topic_fn=_generate_category,
    overwrite=overwrite,
    remote=remote,
    category=True,
    task_id=task_id,
  )

  # At this point we have something like this in output_path:
  # {
  #   'cluster_id': 0,
  #   'cluster_membership_prob': 1.0,
  #   'cluster_title': '...',
  #   'cluster_title__cluster': {
  #      'cluster_id': 1, 'cluster_membership_prob': 1.0, 'cluster_title': '...'
  #   }
  # }
  # and we want to flatten it to:
  # {
  #   'cluster_id': 0,
  #   'cluster_membership_prob': 1.0,
  #   'cluster_title': '...',
  #   'category_id': 1,
  #   'category_membership_prob': 1.0,
  #   'category_title': '...',
  # }
  CLUSTER_FIELD = category_cluster_output_path[-1]

  def flatten_cluster_info(item: Item) -> Item:
    if CLUSTER_FIELD not in item:
      return item
    return {
      CLUSTER_ID: item.get(CLUSTER_ID),
      CLUSTER_MEMBERSHIP_PROB: item.get(CLUSTER_MEMBERSHIP_PROB),
      CLUSTER_TITLE: item.get(CLUSTER_TITLE),
      CATEROGY_ID: item[CLUSTER_FIELD].get(CLUSTER_ID),
      CATEGORY_MEMBERSHIP_PROB: item[CLUSTER_FIELD].get(CLUSTER_MEMBERSHIP_PROB),
      CATEGORY_TITLE: item[CLUSTER_FIELD].get(CLUSTER_TITLE),
    }

  dataset.map(
    flatten_cluster_info,
    cluster_output_path,
    cluster_output_path,
    overwrite=True,
    schema=field(
      fields={
        CLUSTER_ID: field('int32', categorical=True),
        CLUSTER_MEMBERSHIP_PROB: 'float32',
        CLUSTER_TITLE: 'string',
        CATEROGY_ID: field('int32', categorical=True),
        CATEGORY_MEMBERSHIP_PROB: 'float32',
        CATEGORY_TITLE: 'string',
      },
      cluster=ClusterInfo(
        min_cluster_size=min_cluster_size,
        remote=remote,
        input_path=(get_callable_name(input),) if callable(input) else input_path,
      ),
    ),
  )
  # Delete the cluster titles.
  dataset.delete_column(title_output_path)
  # Delete the caterogy clusters.
  dataset.delete_column(category_cluster_output_path)
  # Delete the category titles.
  dataset.delete_column((*category_cluster_output_path, CLUSTER_TITLE))

  if task_id:
    task_manager.set_completed(task_id)


def _cluster(
  docs: Iterator[str],
  min_cluster_size: int = MIN_CLUSTER_SIZE,
  remote: bool = False,
) -> Iterator[Item]:
  """Cluster docs with HDBSCAN."""
  if remote:
    remote_fn = modal.Function.lookup('cluster', 'Cluster.cluster').remote
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
    from cuml.cluster.hdbscan import HDBSCAN  # type: ignore
  except ImportError:
    from sklearn.cluster import HDBSCAN

  with DebugTimer('HDBSCAN: Clustering'):
    min_cluster_size = min(min_cluster_size, len(all_vectors))
    hdbscan = HDBSCAN(min_cluster_size=min_cluster_size, n_jobs=-1)
    hdbscan.fit(all_vectors)

  for cluster_id, membership_prob in zip(hdbscan.labels_, hdbscan.probabilities_):
    cluster_id = int(cluster_id)
    membership_prob = float(membership_prob)
    item = {CLUSTER_ID: cluster_id, CLUSTER_MEMBERSHIP_PROB: membership_prob}
    if cluster_id < 0:
      item = {CLUSTER_ID: -1}
    yield item
