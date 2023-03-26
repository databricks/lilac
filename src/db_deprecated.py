"""Methods for interfacing with the db."""
import itertools
import os
import re
import time
from typing import Iterable, Optional, TypeVar, cast

import cohere
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import normalize

from datasets import DatasetDict, load_dataset  # type: ignore

from .constants import (
    DATA_JSON_FILENAME,
    EMBEDDINGS_FILENAME,
    Dataset,
    DatasetRow,
    LabeledExample,
    data_path,
)
from .server_api import (
    AddDatasetOptions,
    AddExamplesOptions,
    GetModelInfoOptions,
    ListModelsResponse,
    LoadModelOptions,
    LoadModelResponse,
    ModelInfo,
    SaveModelOptions,
    SearchExamplesOptions,
    SearchExamplesResult,
    SearchExamplesRowResult,
)
from .utils import get_output_dir, log, open_file

PREFIX = ''
co = cohere.Client(os.environ['COHERE_API_KEY'])

BATCH_SIZE = 96
DATA_DIR = '/Users/niku/Code/datasets/jigsaw-toxic-comment-classification-challenge'


def list_models() -> ListModelsResponse:
  """List the models found in gcs_cache."""
  model_infos: list[ModelInfo] = []
  for root, _, files in os.walk(data_path()):
    if len(files) > 0:
      subdir = root[len(data_path() + '/'):]
      split = list(filter(lambda path: path != '', os.path.split(subdir)))
      if len(split) == 2:  # The subdir is a (username, model_name)
        username, model_name = split
        model_infos.append(ModelInfo(username=username, name=model_name, description=''))

  return ListModelsResponse(models=model_infos)


def get_model_info(options: GetModelInfoOptions) -> ModelInfo:
  """Read the model info."""
  return ModelInfo(username=options.username, name=options.name, description='')


def _fix_text(text: str) -> str:
  # Fix extra spacing before punctuation. E.g. "I like it ." -> "I like it.".
  text = re.sub(' ([,.;?!:])', '\\1', text)
  # Fix extra spacing around quotes. E.g. 'He said: " I like it "' -> 'He said: "I like it"'.
  text = re.sub('" (.*?) "', '"\\1"', text)
  text = re.sub("' (.*?) '", "'\\1'", text)
  # Remove brackets. E.g. '[I] like it' -> 'I like it'.
  text = re.sub('\\[ ?(.*?) ?\\]', '\\1', text)
  # Remove parentheses. E.g. '(I) like it' -> 'I like it'.
  text = re.sub('\\( ?(.*?) ?\\)', '\\1', text)
  return text


def _compute_embedding(texts: list[str]) -> np.ndarray:
  texts = [_fix_text(PREFIX + text) for text in texts]
  cohere_embeddings = co.embed(texts, truncate='START').embeddings
  return normalize(np.array(cohere_embeddings)).astype(np.float16)


def _save_dataset(model_info: ModelInfo, dataset: Dataset, embeddings: np.ndarray) -> None:
  dataset_json = dataset.json()

  gcs_dir = get_output_dir(data_path(), model_info.username, model_info.name)
  gcs_path = os.path.join(gcs_dir, DATA_JSON_FILENAME)
  with open_file(gcs_path, 'w') as f:
    f.write(dataset_json)

  embeddings_gcs_path = os.path.join(gcs_dir, EMBEDDINGS_FILENAME)
  with open_file(embeddings_gcs_path, 'wb') as f:
    np.save(f, embeddings)


Tchunk = TypeVar('Tchunk')


def chunks(iterable: Iterable[Tchunk], size: int) -> Iterable[list[Tchunk]]:
  """Split a list of items into equal-sized chunks. The last chunk might be smaller."""
  it = iter(iterable)
  chunk = list(itertools.islice(it, size))
  while chunk:
    yield chunk
    chunk = list(itertools.islice(it, size))


def add_df(df: pd.DataFrame, username: str, model_name: str, text_col: str,
           metadata_cols: list[str]) -> None:
  """Add a pandas dataframe to a model."""
  text_series = df[text_col]
  metadata_series = [df[metadata_col] for metadata_col in metadata_cols]
  dataset_rows: list[DatasetRow] = []
  for text, *metadata in zip(text_series, *metadata_series):
    metadata_dict: dict[str, str] = {}
    for metadata, metadata_col in zip(metadata, metadata_cols):
      metadata_dict[metadata_col] = metadata
    dataset_rows.append(DatasetRow(text=text, metadata=metadata_dict, prediction=0))

  chunked_embeddings = [
      np.array(_compute_embedding([row.text
                                   for row in chunk]))
      for chunk in chunks(dataset_rows, size=96)
  ]
  embeddings = np.concatenate(chunked_embeddings)
  _save_dataset(ModelInfo(username=username, name=model_name, description=''),
                Dataset(data=dataset_rows, labeled_data=[]), embeddings)


def add_dataset(options: AddDatasetOptions) -> None:
  """Add a dataset to a model."""
  model_info = get_model_info(
      GetModelInfoOptions(username=options.username, name=options.model_name))
  start_time = time.time()

  hf_dataset = cast(
      DatasetDict,
      load_dataset(options.hf_dataset, split=options.hf_split, data_dir=DATA_DIR).shuffle())

  # Set the prediction to 0 when there's no model so all data is in "out of filter".
  dataset = [DatasetRow(text=text, prediction=0) for text in hf_dataset[options.hf_text_field]]

  def _process_embeddings(batch: dict) -> dict:
    return {'embeddings': _compute_embedding(batch[options.hf_text_field])}

  # Compute embeddings.
  print('Computing embeddings...')
  dataset_embeddings = hf_dataset.map(_process_embeddings, batched=True, batch_size=BATCH_SIZE)

  all_embeddings = np.array(dataset_embeddings['embeddings'])

  _save_dataset(model_info, Dataset(data=dataset, labeled_data=[]), all_embeddings)

  log(f'[DB] Writing data and embeddings took {time.time() - start_time}s.')


# Maps a username/model_name to a [dataset, embeddings] matrix.
MODEL_CACHE: dict[str, tuple[Dataset, np.ndarray]] = {}


def load_model(options: LoadModelOptions) -> LoadModelResponse:
  """Load a model and returns all the data to the frontend."""
  dataset: Optional[Dataset] = None

  cache_key = f'{options.username}/{options.name}'
  if cache_key in MODEL_CACHE:
    dataset, _ = MODEL_CACHE[cache_key]
    return LoadModelResponse(dataset=dataset, has_data=True)

  try:
    gcs_dir = get_output_dir(data_path(), options.username, options.name)
    gcs_path = os.path.join(gcs_dir, DATA_JSON_FILENAME)
    with open_file(gcs_path) as f:
      dataset = Dataset.parse_raw(f.read())

    embeddings_gcs_path = os.path.join(gcs_dir, EMBEDDINGS_FILENAME)
    with open_file(embeddings_gcs_path, 'rb') as f:
      embeddings = np.load(f)

    MODEL_CACHE[cache_key] = (dataset, embeddings)
    has_data = True
  except Exception as e:
    print('Error loading model:', e)
    has_data = False

  return LoadModelResponse(dataset=dataset, has_data=has_data)


def save_model(options: SaveModelOptions) -> None:
  """Load a model and returns all the data to the frontend."""
  model_info = get_model_info(GetModelInfoOptions(username=options.username, name=options.name))

  dataset: Optional[Dataset] = None

  cache_key = f'{model_info.username}/{model_info.name}'
  if cache_key in MODEL_CACHE:
    dataset, embeddings = MODEL_CACHE[cache_key]
    dataset.labeled_data = options.labeled_data

    # Train the new linear model with the training data.
    model = LogisticRegression(solver='liblinear', warm_start=False, class_weight='balanced')
    train_embedding_idxs: list[int] = []
    labels: list[int] = []
    for train_data_row in dataset.labeled_data:
      train_embedding_idxs.append(train_data_row.row_idx)
      labels.append(train_data_row.label)

    train_embeddings = embeddings[train_embedding_idxs]
    predictions = []
    prediction_probs = []
    if len(train_embeddings) > 0:
      model.fit(train_embeddings, labels)
      # Add predictions to every point.
      predictions = model.predict(embeddings)
      prediction_probs = model.predict_proba(embeddings)

    # Add sortable metadata.
    for i, example in enumerate(dataset.data):
      if len(predictions):
        prediction, confidence = int(predictions[i]), prediction_probs[i][1]
      else:
        # Zero out the confidence and the prediction.
        prediction, confidence = 0, 0.0

      example.prediction, example.metadata['confidence'] = prediction, confidence

    _save_dataset(model_info, dataset, embeddings)
  else:
    raise ValueError(f'{cache_key} not in cache!')


def add_examples(options: AddExamplesOptions) -> None:
  """Add examples (currently training) to the dataset."""
  model_info = get_model_info(GetModelInfoOptions(username=options.username, name=options.name))

  dataset: Optional[Dataset] = None

  cache_key = f'{model_info.username}/{model_info.name}'
  if cache_key in MODEL_CACHE:
    dataset, embeddings = MODEL_CACHE[cache_key]

    new_embeddings = _compute_embedding([example.text for example in options.examples])
    new_example_idx = len(dataset.data)
    for i, example in enumerate(options.examples):
      dataset.data.append(DatasetRow(text=example.text))
      dataset.labeled_data.append(LabeledExample(row_idx=i + new_example_idx, label=example.label))
    # Add the new embeddings.
    MODEL_CACHE[cache_key] = (dataset, np.vstack([embeddings, new_embeddings]))
  else:
    raise ValueError(f'{cache_key} not in cache!')


def search_examples(options: SearchExamplesOptions) -> SearchExamplesResult:
  """Search examples from the dataset using embedding similarity."""
  search_embedding = _compute_embedding([options.query]).flatten()
  cache_key = f'{options.username}/{options.model_name}'
  if cache_key in MODEL_CACHE:
    _, embeddings = MODEL_CACHE[cache_key]
    similarities = np.dot(embeddings, search_embedding)

    k = 500
    idx = np.argpartition(similarities, -k)[-k:]  # Indices not sorted

    idx = idx[np.argsort(
        similarities[idx])][::-1]  # Indices sorted by value from largest to smallest

    topk_similarities = similarities[idx]
  else:
    raise ValueError('No model!')

  return SearchExamplesResult(row_results=[
      SearchExamplesRowResult(row_idx=row_idx, similarity=similarity)
      for (row_idx, similarity) in zip(idx, topk_similarities)
  ])
