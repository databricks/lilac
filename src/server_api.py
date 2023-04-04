"""The REST API for the server."""

from typing import Optional

from pydantic import BaseModel, validator

from .constants import AddExample, Dataset, LabeledExample
from .datasets.db_dataset import DatasetManifest, SortOrder
from .signals.signal import Signal
from .signals.signal_registry import resolve_signal


# Mirrors the CreateModelOptions in server_api.ts.
class CreateModelOptions(BaseModel):
  """Options to create a model. Body of the POST request to /db/create_model."""
  username: str
  name: str
  description: str


class GetModelInfoOptions(BaseModel):
  """Options to get a single model."""
  username: str
  name: str


class CreateModelResponse(BaseModel):
  """Options to create a model. Body of the POST request to /db/create_model."""
  username: str
  name: str


class ModelInfo(BaseModel):
  """Information about a model."""
  username: str
  name: str
  description: str


class ListModelsResponse(BaseModel):
  """The response object of /db/list_models."""
  models: list[ModelInfo]


class AddDatasetOptions(BaseModel):
  """The request for the create model spec endpoint."""
  username: str
  model_name: str

  # Huggingface data loading.
  hf_dataset: str
  hf_split: str = 'train'
  hf_text_field: str = 'text'


class LoadModelOptions(BaseModel):
  """The request for the create model spec endpoint."""
  username: str
  name: str


class SaveModelOptions(BaseModel):
  """The request for the save model to GCS endpoint."""
  username: str
  name: str
  labeled_data: list[LabeledExample]


class AddExamplesOptions(BaseModel):
  """The request for the add examples endpoint."""
  username: str
  name: str
  examples: list[AddExample]


class SearchExamplesOptions(BaseModel):
  """The request for the search examples endpoint."""
  username: str
  model_name: str
  query: str


class SearchExamplesRowResult(BaseModel):
  """The response of the search examples endpoint."""
  row_idx: int
  similarity: float


class SearchExamplesResult(BaseModel):
  """The response of the search examples endpoint."""
  row_results: list[SearchExamplesRowResult]


class LoadModelResponse(BaseModel):
  """The request for the create model spec endpoint."""
  dataset: Optional[Dataset]
  has_data: bool


class ModelPredictOptions(BaseModel):
  """The request for the model predict endpoint."""
  username: str
  model_name: str
  text: str


class ModelPredictResponse(BaseModel):
  """The response for the model predict endpoint."""
  prediction: int


class WebEnrichmentInfo(BaseModel):
  """Information about an enrichmed column."""
  signal_name: str
  column_enriched: str


class WebColumnInfo(BaseModel):
  """Information about a column."""
  name: str
  enrichment: Optional[WebEnrichmentInfo]


class WebManifest(BaseModel):
  """Information about a dataset."""
  dataset_manifest: DatasetManifest


# Dataset DB methods.
class SelectDatasetRowsOptions(BaseModel):
  """The request for the select dataset rows endpoint."""

  columns: Optional[str] = None
  filters: Optional[str] = None
  sort_by: Optional[str] = None
  sort_order: Optional[SortOrder] = SortOrder.DESC
  limit: Optional[int] = None


class ComputeSignalOptions(BaseModel):
  """The request for the compute signal endpoint."""
  signal: Signal

  # The columns to compute the signal on.
  column: str

  @validator('signal', pre=True)
  def parse_signal(cls, signal: dict) -> Signal:
    """Parse a signal to its specific subclass instance."""
    return resolve_signal(signal)


class ComputeEmbeddingIndexOptions(BaseModel):
  """The request for the compute embedding index endpoint."""
  embedding: str

  # The columns to compute the signal on.
  column: str
