"""Router for the concept database."""

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .concepts.concept import Concept, ConceptModel
from .concepts.db_concept import (
    DISK_CONCEPT_DB,
    DISK_CONCEPT_MODEL_DB,
    ConceptUpdate,
)

router = APIRouter()


@router.get('/{namespace}/{concept_name}', response_model_exclude_none=True)
def get_concept(namespace: str, concept_name: str) -> Concept:
  """Get a concept from a database."""
  concept = DISK_CONCEPT_DB.get(namespace, concept_name)
  if not concept:
    raise HTTPException(status_code=404,
                        detail=f'Concept "{namespace}/{concept_name}" was not found')
  return concept


@router.post('/{namespace}/{concept_name}', response_model_exclude_none=True)
def post_concept(namespace: str, concept_name: str, change: ConceptUpdate) -> Concept:
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
  model_updated: bool


class ConceptModelResponse(BaseModel):
  """Response body for the get_concept_model endpoint."""
  model: ConceptModel
  model_updated: bool


@router.get('/{namespace}/{concept_name}/{embedding_name}')
def get_concept_model(namespace: str, concept_name: str, embedding_name: str) -> dict:
  """Get a concept model from a database."""
  concept = DISK_CONCEPT_DB.get(namespace, concept_name)
  if not concept:
    raise HTTPException(status_code=404,
                        detail=f'Concept "{namespace}/{concept_name}" was not found')

  model = DISK_CONCEPT_MODEL_DB.get(namespace, concept_name, embedding_name)
  if not model:
    raise HTTPException(
        status_code=404,
        detail=f'Concept model "{namespace}/{concept_name}/{embedding_name}" was not found')

  model_updated = DISK_CONCEPT_MODEL_DB.sync(model)
  return ConceptModelResponse(model=model, model_updated=model_updated).dict(exclude_none=True)


@router.post('/{namespace}/{concept_name}/{embedding_name}/score', response_model_exclude_none=True)
def score(namespace: str, concept_name: str, embedding_name: str, body: ScoreBody) -> ScoreResponse:
  """Score examples along the specified concept."""
  concept = DISK_CONCEPT_DB.get(namespace, concept_name)
  if not concept:
    raise HTTPException(status_code=404,
                        detail=f'Concept "{namespace}/{concept_name}" was not found')
  model = DISK_CONCEPT_MODEL_DB.get(namespace, concept_name, embedding_name)
  if not model:
    raise HTTPException(
        status_code=404,
        detail=f'Concept model "{namespace}/{concept_name}/{embedding_name}" was not found')

  model_updated = DISK_CONCEPT_MODEL_DB.sync(model)
  # TODO(smilkov): Support images.
  texts = [example.text or '' for example in body.examples]
  return ScoreResponse(scores=model.score(texts), model_updated=model_updated)
