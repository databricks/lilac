"""Functions for generating titles and categories for clusters of documents."""

import functools
import random
from typing import Any, Iterator, Optional, Sequence, cast

import instructor
import modal
from instructor.exceptions import IncompleteOutputException
from joblib import Parallel, delayed
from pydantic import (
  BaseModel,
)
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_random_exponential

from ..batch_utils import group_by_sorted_key_iter
from ..schema import (
  Item,
)
from ..signal import (
  TopicFn,
  TopicFnBatched,
  TopicFnNoBatch,
)
from ..tasks import TaskInfo
from ..utils import chunks, log
from ..env import env

_TOP_K_CENTRAL_DOCS = 7
_TOP_K_CENTRAL_TITLES = 20
_NUM_THREADS = 32
_NUM_RETRIES = 16
# OpenAI rate limits you on `max_tokens` so we ideally want to guess the right value. If ChatGPT
# fails to generate a title within the `max_tokens` limit, we will retry with a higher value.
_OPENAI_INITIAL_MAX_TOKENS = 50
_OPENAI_FINAL_MAX_TOKENS = 200

TITLE_SYSTEM_PROMPT = (
  'You are a world-class short title generator. Ignore the related snippets below '
  'and generate a short title (5 words maximum) to describe their common theme. Some examples: '
  '"YA book reviews", "Questions about South East Asia", "Translating English to '
  'Polish", "Writing product descriptions", etc. If the '
  "snippet's language is different than English, mention it in the title, e.g. "
  '"Recipes in Spanish". Avoid vague words like "various", "assortment", '
  '"comments", "discussion", "requests", etc.'
)
EXAMPLE_MATH_SNIPPETS = [
  (
    'Explain each computation step in the evaluation of 90504690 / 37364. Exclude words; show only '
    'the math.'
  ),
  'What does 3-9030914617332 yield? Only respond with math and no words.',
  'Provide a step-by-step calculation for 224 * 276429. Exclude words; show only the math.',
]

EXAMPLE_SNIPPETS = '\n'.join(
  [f'BEGIN_SNIPPET\n{doc}\nEND_SNIPPET' for doc in EXAMPLE_MATH_SNIPPETS]
)
EXAMPLE_TITLE = 'Mathematical Calculations'

CATEGORY_SYSTEM_PROMPT = (
  'You are a world-class category generator. Generate a short category name (one or two words '
  'long) for the provided titles. Do not use parentheses and do not generate alternative names.'
)
CATEGORY_EXAMPLE_TITLES = '\n'.join(
  [
    'Graph Theory and Tree Counting Problems',
    'Mathematical Problem Solving and Calculations',
    'Pizza Mathematics and Optimization',
    'Mathematical Equations and Operations',
  ]
)
EXAMPLE_CATEGORY = 'Category: Mathematics'

_SHORTEN_LEN = 400


def get_titling_snippet(text: str) -> str:
  """Shorten the text to a snippet for titling."""
  text = text.strip()
  if len(text) <= _SHORTEN_LEN:
    return text
  prefix_len = _SHORTEN_LEN // 2
  return text[:prefix_len] + '\n...\n' + text[-prefix_len:]


class ChatMessage(BaseModel):
  """Message in a conversation."""

  role: str
  content: str


class SamplingParams(BaseModel):
  """Sampling parameters for the mistral model."""

  temperature: float = 0.0
  top_p: float = 1.0
  max_tokens: int = 50
  stop: Optional[str] = None
  spaces_between_special_tokens: bool = False


class MistralInstructRequest(BaseModel):
  """Request to embed a list of documents."""

  chats: list[list[ChatMessage]]
  sampling_params: SamplingParams = SamplingParams()


class MistralInstructResponse(BaseModel):
  """Response from the Mistral model."""

  outputs: list[str]


def generate_category_mistral(batch_titles: list[list[tuple[str, float]]]) -> list[str]:
  """Summarize a group of titles into a category."""
  remote_fn = modal.Function.lookup('mistral-7b', 'Instruct.generate').remote
  request = MistralInstructRequest(chats=[], sampling_params=SamplingParams(stop='\n'))
  for ranked_titles in batch_titles:
    # Get the top 5 titles.
    titles = [title for title, _ in ranked_titles[:_TOP_K_CENTRAL_DOCS]]
    snippets = '\n'.join(titles)
    messages: list[ChatMessage] = [
      ChatMessage(role='system', content=CATEGORY_SYSTEM_PROMPT),
      ChatMessage(role='user', content=CATEGORY_EXAMPLE_TITLES),
      ChatMessage(role='assistant', content=EXAMPLE_CATEGORY),
      ChatMessage(role='user', content=snippets),
    ]
    request.chats.append(messages)

  category_prefix = 'category: '

  # TODO(smilkov): Add retry logic.
  def request_with_retries() -> list[str]:
    response_dict = remote_fn(request.model_dump())
    response = MistralInstructResponse.model_validate(response_dict)
    result: list[str] = []
    for title in response.outputs:
      title = title.strip()
      if title.lower().startswith(category_prefix):
        title = title[len(category_prefix) :]
      result.append(title)
    return result

  return request_with_retries()


def generate_title_mistral(batch_docs: list[list[tuple[str, float]]]) -> list[str]:
  """Summarize a group of requests in a title of at most 5 words."""
  remote_fn = modal.Function.lookup('mistral-7b', 'Instruct.generate').remote
  request = MistralInstructRequest(chats=[], sampling_params=SamplingParams(stop='\n'))
  for ranked_docs in batch_docs:
    # Get the top 5 documents.
    docs = [doc for doc, _ in ranked_docs[:_TOP_K_CENTRAL_DOCS]]
    snippets = '\n'.join(
      [f'BEGIN_SNIPPET\n{get_titling_snippet(doc)}\nEND_SNIPPET' for doc in docs]
    )
    messages: list[ChatMessage] = [
      ChatMessage(role='system', content=TITLE_SYSTEM_PROMPT),
      ChatMessage(role='user', content=EXAMPLE_SNIPPETS),
      ChatMessage(role='assistant', content=EXAMPLE_TITLE),
      ChatMessage(role='user', content=snippets),
    ]
    request.chats.append(messages)

  title_prefix = 'title: '

  # TODO(smilkov): Add retry logic.
  def request_with_retries() -> list[str]:
    response_dict = remote_fn(request.model_dump())
    response = MistralInstructResponse.model_validate(response_dict)
    result: list[str] = []
    for title in response.outputs:
      title = title.strip()
      if title.lower().startswith(title_prefix):
        title = title[len(title_prefix) :]
      result.append(title)
    return result

  return request_with_retries()


@functools.cache
def _openai_client() -> Any:
  """Get an OpenAI client."""
  api_base = env('OPENAI_API_BASE')
  try:
    import openai


  except ImportError:
    raise ImportError(
      'Could not import the "openai" python package. '
      'Please install it with `pip install openai`.'
    )

  # OpenAI requests sometimes hang, without any errors, and the default connection timeout is 10
  # mins, which is too long. Set it to 7 seconds (99%-tile for latency is 3-4 sec). Also set
  # `max_retries` to 0 to disable internal retries so we handle retries ourselves.
  return instructor.patch(openai.OpenAI(timeout=7, max_retries=0, base_url=api_base))


class Title(BaseModel):
  """A 4-5 word title for the group of related snippets."""

  title: str


def generate_title_openai(ranked_docs: list[tuple[str, float]]) -> str:
  """Generate a short title for a set of documents using OpenAI."""
  # Get the top 5 documents.
  docs = [doc for doc, _ in ranked_docs[:_TOP_K_CENTRAL_DOCS]]
  texts = [f'BEGIN_SNIPPET\n{get_titling_snippet(doc)}\nEND_SNIPPET' for doc in docs]
  input = '\n'.join(texts)
  try:
    import openai

  except ImportError:
    raise ImportError(
      'Could not import the "openai" python package. '
      'Please install it with `pip install openai`.'
    )

  @retry(
    retry=retry_if_exception_type(
      (
        openai.RateLimitError,
        openai.APITimeoutError,
        openai.APIConnectionError,
        openai.ConflictError,
        openai.InternalServerError,
      )
    ),
    wait=wait_random_exponential(multiplier=0.5, max=60),
    stop=stop_after_attempt(_NUM_RETRIES),
  )
  def request_with_retries() -> str:
    api_model = env('API_MODEL')
    max_tokens = _OPENAI_INITIAL_MAX_TOKENS
    while max_tokens <= _OPENAI_FINAL_MAX_TOKENS:
      try:
        title = _openai_client().chat.completions.create(
          model=api_model,
          response_model=Title,
          temperature=0.0,
          max_tokens=max_tokens,
          messages=[
            {
              'role': 'system',
              'content': TITLE_SYSTEM_PROMPT,
            },
            {'role': 'user', 'content': input},
          ],
        )
        return title.title
      except IncompleteOutputException:
        max_tokens += _OPENAI_INITIAL_MAX_TOKENS
        log(f'Retrying with max_tokens={max_tokens}')
    log(f'Could not generate a short title for input:\n{input}')
    # We return a string instead of None, since None is emitted when the text column is sparse.
    return 'FAILED_TO_TITLE'

  return request_with_retries()


class Category(BaseModel):
  """A short category title."""

  category: str


def generate_category_openai(ranked_docs: list[tuple[str, float]]) -> str:
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
    retry=retry_if_exception_type(
      (
        openai.RateLimitError,
        openai.APITimeoutError,
        openai.APIConnectionError,
        openai.ConflictError,
        openai.InternalServerError,
      )
    ),
    wait=wait_random_exponential(multiplier=0.5, max=60),
    stop=stop_after_attempt(_NUM_RETRIES),
  )
  def request_with_retries() -> str:
    api_model = env('API_MODEL')
    max_tokens = _OPENAI_INITIAL_MAX_TOKENS
    while max_tokens <= _OPENAI_FINAL_MAX_TOKENS:
      try:
        category = _openai_client().chat.completions.create(
          model=api_model,
          response_model=Category,
          temperature=0.0,
          max_tokens=max_tokens,
          messages=[
            {
              'role': 'system',
              'content': (
                'You are a world-class category labeler. Generate a short category name for the '
                'provided titles. For example, given two titles "translating english to polish" '
                'and "translating korean to english", generate "Translation".'
              ),
            },
            {'role': 'user', 'content': input},
          ],
        )
        return category.category
      except IncompleteOutputException:
        max_tokens += _OPENAI_INITIAL_MAX_TOKENS
        log(f'Retrying with max_tokens={max_tokens}')
    log(f'Could not generate a short category for input:\n{input}')
    return 'FAILED_TO_GENERATE'

  return request_with_retries()


def compute_titles(
  items: Iterator[Item],
  text_column: str,
  cluster_id_column: str,
  membership_column: str,
  topic_fn: TopicFn,
  batch_size: Optional[int] = None,
  task_info: Optional[TaskInfo] = None,
) -> Iterator[str]:
  """Compute titles for clusters of documents."""

  def _compute_title(
    batch_docs: list[list[tuple[str, float]]], group_size: list[int]
  ) -> list[tuple[int, Optional[str]]]:
    if batch_size is None:
      topic_fn_no_batch = cast(TopicFnNoBatch, topic_fn)
      topics: Sequence[Optional[str]]
      if batch_docs and batch_docs[0]:
        topics = [topic_fn_no_batch(batch_docs[0])]
      else:
        topics = [None]
    else:
      topic_fn_batched = cast(TopicFnBatched, topic_fn)
      topics = topic_fn_batched(batch_docs)
    return [(group_size, topic) for group_size, topic in zip(group_size, topics)]

  def _delayed_compute_all_titles() -> Iterator:
    clusters = group_by_sorted_key_iter(items, lambda x: x[cluster_id_column])
    for batch_clusters in chunks(clusters, batch_size or 1):
      cluster_sizes: list[int] = []
      batch_docs: list[list[tuple[str, float]]] = []
      for cluster in batch_clusters:
        sorted_docs: list[tuple[str, float]] = []

        for item in cluster:
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

        # Remove any duplicate texts in the cluster.
        sorted_docs = list(set(sorted_docs))

        # Shuffle the cluster to avoid biasing the topic function.
        random.shuffle(sorted_docs)

        # Sort the cluster by membership probability after shuffling so that we still choose high
        # membership scores but they are still shuffled when the values are equal.
        sorted_docs.sort(key=lambda text_score: text_score[1], reverse=True)
        cluster_sizes.append(len(cluster))
        batch_docs.append(sorted_docs)

      yield delayed(_compute_title)(batch_docs, cluster_sizes)

  parallel = Parallel(n_jobs=_NUM_THREADS, backend='threading', return_as='generator')
  if task_info:
    task_info.total_progress = 0
  for batch_result in parallel(_delayed_compute_all_titles()):
    for group_size, title in batch_result:
      if task_info:
        task_info.total_progress += group_size
      for _ in range(group_size):
        yield title
