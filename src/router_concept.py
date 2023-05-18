"""Router for the concept database."""

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .concepts.concept import Concept, ConceptModel
from .concepts.db_concept import DISK_CONCEPT_DB, DISK_CONCEPT_MODEL_DB, ConceptInfo, ConceptUpdate
from .router_utils import RouteErrorHandler

router = APIRouter(route_class=RouteErrorHandler)


@router.get('/', response_model_exclude_none=True)
def get_concepts() -> list[ConceptInfo]:
  """List the concepts."""
  return DISK_CONCEPT_DB.list()


@router.get('/{namespace}/{concept_name}', response_model_exclude_none=True)
def get_concept(namespace: str, concept_name: str) -> Concept:
  """Get a concept from a database."""
  concept = DISK_CONCEPT_DB.get(namespace, concept_name)
  if not concept:
    raise HTTPException(
      status_code=404, detail=f'Concept "{namespace}/{concept_name}" was not found')
  return concept


@router.post('/create', response_model_exclude_none=True)
def create_concept(concept_info: ConceptInfo) -> Concept:
  """Edit a concept in the database."""
  return DISK_CONCEPT_DB.create(concept_info)


@router.post('/{namespace}/{concept_name}', response_model_exclude_none=True)
def edit_concept(namespace: str, concept_name: str, change: ConceptUpdate) -> Concept:
  """Edit a concept in the database."""
  return DISK_CONCEPT_DB.edit(namespace, concept_name, change)


class ScoreExample(BaseModel):
  """Example to score along a specific concept."""
  text: Optional[str]
  img: Optional[bytes]


class ScoreBody(BaseModel):
  """Request body for the score endpoint."""
  examples: list[ScoreExample]


class ScoreResponse(BaseModel):
  """Response body for the score endpoint."""
  scores: list[float]
  model_synced: bool


class ConceptModelResponse(BaseModel):
  """Response body for the get_concept_model endpoint."""
  model: ConceptModel
  model_synced: bool


@router.get('/{namespace}/{concept_name}/{embedding_name}')
def get_concept_model(namespace: str,
                      concept_name: str,
                      embedding_name: str,
                      sync_model: bool = False) -> ConceptModelResponse:
  """Get a concept model from a database."""
  concept = DISK_CONCEPT_DB.get(namespace, concept_name)
  if not concept:
    raise HTTPException(
      status_code=404, detail=f'Concept "{namespace}/{concept_name}" was not found')

  model = DISK_CONCEPT_MODEL_DB.get(namespace, concept_name, embedding_name)
  if not model:
    raise HTTPException(
      status_code=404,
      detail=f'Concept model "{namespace}/{concept_name}/{embedding_name}" was not found')

  if sync_model:
    model_synced = DISK_CONCEPT_MODEL_DB.sync(model)
  else:
    model_synced = DISK_CONCEPT_MODEL_DB.in_sync(model)
  return ConceptModelResponse(model=model, model_synced=model_synced)


@router.post('/{namespace}/{concept_name}/{embedding_name}/score', response_model_exclude_none=True)
def score(namespace: str, concept_name: str, embedding_name: str, body: ScoreBody) -> ScoreResponse:
  """Score examples along the specified concept."""
  concept = DISK_CONCEPT_DB.get(namespace, concept_name)
  if not concept:
    raise HTTPException(
      status_code=404, detail=f'Concept "{namespace}/{concept_name}" was not found')
  model = DISK_CONCEPT_MODEL_DB.get(namespace, concept_name, embedding_name)
  if not model:
    raise HTTPException(
      status_code=404,
      detail=f'Concept model "{namespace}/{concept_name}/{embedding_name}" was not found')

  model_updated = DISK_CONCEPT_MODEL_DB.sync(model)
  # TODO(smilkov): Support images.
  texts = [example.text or '' for example in body.examples]
  return ScoreResponse(scores=model.score(texts), model_synced=model_updated)
