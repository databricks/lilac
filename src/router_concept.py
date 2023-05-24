"""Router for the concept database."""

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .concepts.concept import DRAFT_MAIN, Concept, ConceptModel, DraftId, draft_examples
from .concepts.db_concept import DISK_CONCEPT_DB, DISK_CONCEPT_MODEL_DB, ConceptInfo, ConceptUpdate
from .db_manager import get_dataset
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


class CreateConceptOptions(BaseModel):
  """Options for creating a concept."""
  namespace: str
  name: str
  type: SignalInputType

  dataset_namespace: Optional[str] = None
  dataset_name: Optional[str] = None


@router.post('/create', response_model_exclude_none=True)
def create_concept(options: CreateConceptOptions) -> Concept:
  """Edit a concept in the database."""
  if options.dataset_namespace:
    if options.dataset_name is None:
      raise HTTPException(
        status_code=400, detail='Must specify `dataset_name` if `dataset_namespace` is specified')
    dataset = get_dataset(options.dataset_namespace, options.dataset_name)
    dataset._query_df
  return None
  # return DISK_CONCEPT_DB.create(options.namespace, options.name, options.type)


@router.post('/{namespace}/{concept_name}', response_model_exclude_none=True)
def edit_concept(namespace: str, concept_name: str, change: ConceptUpdate) -> Concept:
  """Edit a concept in the database."""
  return DISK_CONCEPT_DB.edit(namespace, concept_name, change)


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


class ConceptModelResponse(BaseModel):
  """Response body for the get_concept_model endpoint."""
  model: ConceptModel
  model_synced: bool


@router.get('/{namespace}/{concept_name}/{embedding_name}')
def get_concept_model(namespace: str,
                      concept_name: str,
                      embedding_name: str,
                      draft: Optional[DraftId] = None,
                      sync_model: bool = False) -> ConceptModelResponse:
  """Get a concept model from a database."""
  concept = DISK_CONCEPT_DB.get(namespace, concept_name)
  if not concept:
    raise HTTPException(
      status_code=404, detail=f'Concept "{namespace}/{concept_name}" was not found')

  manager = DISK_CONCEPT_MODEL_DB.get(namespace, concept_name, embedding_name)
  if not manager:
    raise HTTPException(
      status_code=404,
      detail=f'Concept model "{namespace}/{concept_name}/{embedding_name}" was not found')

  if sync_model:
    model_synced = DISK_CONCEPT_MODEL_DB.sync(manager)
  else:
    model_synced = DISK_CONCEPT_MODEL_DB.in_sync(manager)
  return ConceptModelResponse(
    model=manager.get_model(draft or DRAFT_MAIN), model_synced=model_synced)


@router.post('/{namespace}/{concept_name}/{embedding_name}/score', response_model_exclude_none=True)
def score(namespace: str, concept_name: str, embedding_name: str, body: ScoreBody) -> ScoreResponse:
  """Score examples along the specified concept."""
  concept = DISK_CONCEPT_DB.get(namespace, concept_name)
  if not concept:
    raise HTTPException(
      status_code=404, detail=f'Concept "{namespace}/{concept_name}" was not found')
  manager = DISK_CONCEPT_MODEL_DB.get(namespace, concept_name, embedding_name)
  concept_model = manager.get_model(body.draft)
  if not concept_model:
    raise HTTPException(
      status_code=404,
      detail=f'Concept model "{namespace}/{concept_name}/{embedding_name}" with draft {body.draft} '
      'was not found')

  models_updated = DISK_CONCEPT_MODEL_DB.sync(manager)
  # TODO(smilkov): Support images.
  texts = [example.text or '' for example in body.examples]
  return ScoreResponse(scores=concept_model.score(texts), model_synced=models_updated)
