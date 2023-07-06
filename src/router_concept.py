"""Router for the concept database."""

from typing import Optional

import openai
from fastapi import APIRouter, HTTPException
from openai_function_call import OpenAISchema
from pydantic import BaseModel, Field

from .concepts.concept import (
  DRAFT_MAIN,
  Concept,
  ConceptColumnInfo,
  ConceptMetrics,
  DraftId,
  draft_examples,
)
from .concepts.db_concept import DISK_CONCEPT_DB, DISK_CONCEPT_MODEL_DB, ConceptInfo, ConceptUpdate
from .config import CONFIG
from .router_utils import RouteErrorHandler
from .schema import SignalInputType

router = APIRouter(route_class=RouteErrorHandler)


@router.get('/', response_model_exclude_none=True)
def get_concepts() -> list[ConceptInfo]:
  """List the concepts."""
  return DISK_CONCEPT_DB.list()


@router.get('/{namespace}/{concept_name}', response_model_exclude_none=True)
def get_concept(namespace: str,
                concept_name: str,
                draft: Optional[DraftId] = DRAFT_MAIN) -> Concept:
  """Get a concept from a database."""
  concept = DISK_CONCEPT_DB.get(namespace, concept_name)
  if not concept:
    raise HTTPException(
      status_code=404, detail=f'Concept "{namespace}/{concept_name}" was not found')

  # Only return the examples from the draft.
  concept.data = draft_examples(concept, draft or DRAFT_MAIN)

  return concept


@router.get('/{namespace}/{concept_name}/column_infos')
def get_concept_column_infos(namespace: str, concept_name: str) -> list[ConceptColumnInfo]:
  """Return a list of dataset columns where this concept was applied to."""
  concept = DISK_CONCEPT_DB.get(namespace, concept_name)
  if not concept:
    raise HTTPException(
      status_code=404, detail=f'Concept "{namespace}/{concept_name}" was not found')
  return DISK_CONCEPT_MODEL_DB.get_column_infos(namespace, concept_name)


class CreateConceptOptions(BaseModel):
  """Options for creating a concept."""
  # Namespace of the concept.
  namespace: str
  # Name of the concept.
  name: str
  # Input type (modality) of the concept.
  type: SignalInputType
  description: Optional[str] = None


@router.post('/create', response_model_exclude_none=True)
def create_concept(options: CreateConceptOptions) -> Concept:
  """Edit a concept in the database."""
  return DISK_CONCEPT_DB.create(options.namespace, options.name, options.type, options.description)


@router.post('/{namespace}/{concept_name}', response_model_exclude_none=True)
def edit_concept(namespace: str, concept_name: str, change: ConceptUpdate) -> Concept:
  """Edit a concept in the database."""
  return DISK_CONCEPT_DB.edit(namespace, concept_name, change)


@router.delete('/{namespace}/{concept_name}')
def delete_concept(namespace: str, concept_name: str) -> None:
  """Deletes the concept from the database."""
  DISK_CONCEPT_DB.remove(namespace, concept_name)
  # Delete concept models from all datasets that are using this concept.
  DISK_CONCEPT_MODEL_DB.remove_all(namespace, concept_name)


class MergeConceptDraftOptions(BaseModel):
  """Merge a draft into main."""
  draft: DraftId


@router.post('/{namespace}/{concept_name}/merge_draft', response_model_exclude_none=True)
def merge_concept_draft(namespace: str, concept_name: str,
                        options: MergeConceptDraftOptions) -> Concept:
  """Merge a draft in the concept into main."""
  return DISK_CONCEPT_DB.merge_draft(namespace, concept_name, options.draft)


class ScoreExample(BaseModel):
  """Example to score along a specific concept."""
  text: Optional[str]
  img: Optional[bytes]


class ScoreBody(BaseModel):
  """Request body for the score endpoint."""
  examples: list[ScoreExample]
  draft: str = DRAFT_MAIN


class ScoreResponse(BaseModel):
  """Response body for the score endpoint."""
  scores: list[float]
  model_synced: bool


class ConceptModelInfo(BaseModel):
  """Information about a concept model."""
  namespace: str
  concept_name: str
  embedding_name: str
  version: int
  column_info: Optional[ConceptColumnInfo] = None
  metrics: Optional[ConceptMetrics] = None


@router.get('/{namespace}/{concept_name}/model')
def get_concept_models(namespace: str, concept_name: str) -> list[ConceptModelInfo]:
  """Get a concept model from a database."""
  concept = DISK_CONCEPT_DB.get(namespace, concept_name)
  if not concept:
    raise HTTPException(
      status_code=404, detail=f'Concept "{namespace}/{concept_name}" was not found')
  models = DISK_CONCEPT_MODEL_DB.get_models(namespace, concept_name)
  return [
    ConceptModelInfo(
      namespace=m.namespace,
      concept_name=m.concept_name,
      embedding_name=m.embedding_name,
      version=m.version,
      column_info=m.column_info,
      metrics=m.get_metrics(concept)) for m in models
  ]


@router.get('/{namespace}/{concept_name}/model/{embedding_name}')
def get_concept_model(namespace: str, concept_name: str, embedding_name: str) -> ConceptModelInfo:
  """Get a concept model from a database."""
  concept = DISK_CONCEPT_DB.get(namespace, concept_name)
  if not concept:
    raise HTTPException(
      status_code=404, detail=f'Concept "{namespace}/{concept_name}" was not found')

  model = DISK_CONCEPT_MODEL_DB.get(namespace, concept_name, embedding_name)
  if not model:
    model = DISK_CONCEPT_MODEL_DB.create(namespace, concept_name, embedding_name)
  model_synced = DISK_CONCEPT_MODEL_DB.sync(model)
  model_info = ConceptModelInfo(
    namespace=model.namespace,
    concept_name=model.concept_name,
    embedding_name=model.embedding_name,
    version=model.version,
    column_info=model.column_info,
    metrics=model.get_metrics(concept))
  return model_info


class MetricsBody(BaseModel):
  """Request body for the compute_metrics endpoint."""
  column_info: Optional[ConceptColumnInfo] = None


@router.post(
  '/{namespace}/{concept_name}/model/{embedding_name}/score', response_model_exclude_none=True)
def score(namespace: str, concept_name: str, embedding_name: str, body: ScoreBody) -> ScoreResponse:
  """Score examples along the specified concept."""
  concept = DISK_CONCEPT_DB.get(namespace, concept_name)
  if not concept:
    raise HTTPException(
      status_code=404, detail=f'Concept "{namespace}/{concept_name}" was not found')
  model = DISK_CONCEPT_MODEL_DB.get(namespace, concept_name, embedding_name)
  if model is None:
    model = DISK_CONCEPT_MODEL_DB.create(namespace, concept_name, embedding_name)
  model_updated = DISK_CONCEPT_MODEL_DB.sync(model)
  # TODO(smilkov): Support images.
  texts = [example.text or '' for example in body.examples]
  return ScoreResponse(scores=model.score(body.draft, texts), model_synced=model_updated)


class Examples(OpenAISchema):
  """Generated text examples."""
  examples: list[str] = Field(..., description='List of generated examples')


@router.get('/generate_examples')
def generate_examples(description: str) -> list[str]:
  """Generate positive examples for a given concept using an LLM model."""
  openai.api_key = CONFIG['OPENAI_API_KEY']
  completion = openai.ChatCompletion.create(
    model='gpt-3.5-turbo-0613',
    functions=[Examples.openai_schema],
    messages=[
      {
        'role': 'system',
        'content': 'You must call the `Examples` function with the generated sentences.',
      },
      {
        'role': 'user',
        'content': f'Give me 5 diverse examples of sentences that demonstrate "{description}"',
      },
    ],
  )
  result = Examples.from_response(completion)
  return result.examples
