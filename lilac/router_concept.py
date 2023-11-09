"""Router for the concept database."""

from typing import Annotated, Iterable, Optional, cast

from fastapi import APIRouter, HTTPException
from fastapi.params import Depends
from instructor import OpenAISchema
from pydantic import BaseModel, Field

from .auth import UserInfo, get_session_user
from .concepts.concept import (
  DRAFT_MAIN,
  Concept,
  ConceptMetadata,
  ConceptMetrics,
  ConceptType,
  DraftId,
  draft_examples,
)
from .concepts.db_concept import DISK_CONCEPT_DB, DISK_CONCEPT_MODEL_DB, ConceptInfo, ConceptUpdate
from .env import env
from .router_utils import RouteErrorHandler, server_compute_concept
from .schema import RichData
from .signals.concept_scorer import ConceptSignal

router = APIRouter(route_class=RouteErrorHandler)


@router.get('/', response_model_exclude_none=True)
def get_concepts(
  user: Annotated[Optional[UserInfo], Depends(get_session_user)]
) -> list[ConceptInfo]:
  """List the concepts."""
  return DISK_CONCEPT_DB.list(user)


@router.get('/{namespace}/{concept_name}', response_model_exclude_none=True)
def get_concept(
  namespace: str,
  concept_name: str,
  draft: Optional[DraftId] = DRAFT_MAIN,
  user: Annotated[Optional[UserInfo], Depends(get_session_user)] = None,
) -> Concept:
  """Get a concept from a database."""
  concept = DISK_CONCEPT_DB.get(namespace, concept_name, user)
  if not concept:
    raise HTTPException(
      status_code=404,
      detail=f'Concept "{namespace}/{concept_name}" was not found or user does not have access.',
    )

  # Only return the examples from the draft.
  concept.data = draft_examples(concept, draft or DRAFT_MAIN)

  return concept


class CreateConceptOptions(BaseModel):
  """Options for creating a concept."""

  # Namespace of the concept.
  namespace: str
  # Name of the concept.
  name: str
  # Input type (modality) of the concept.
  type: ConceptType
  metadata: Optional[ConceptMetadata] = None


@router.post('/create', response_model_exclude_none=True)
def create_concept(
  options: CreateConceptOptions, user: Annotated[Optional[UserInfo], Depends(get_session_user)]
) -> Concept:
  """Edit a concept in the database."""
  return DISK_CONCEPT_DB.create(
    options.namespace, options.name, options.type, metadata=options.metadata, user=user
  )


@router.post('/{namespace}/{concept_name}', response_model_exclude_none=True)
def edit_concept(
  namespace: str,
  concept_name: str,
  change: ConceptUpdate,
  user: Annotated[Optional[UserInfo], Depends(get_session_user)],
) -> Concept:
  """Edit a concept in the database."""
  return DISK_CONCEPT_DB.edit(namespace, concept_name, change, user)


@router.post('/{namespace}/{concept_name}/metadata', response_model_exclude_none=True)
def edit_concept_metadata(
  namespace: str,
  concept_name: str,
  concept_metadata: ConceptMetadata,
  user: Annotated[Optional[UserInfo], Depends(get_session_user)],
) -> None:
  """Edit the metadata of a concept."""
  DISK_CONCEPT_DB.update_metadata(
    namespace=namespace, name=concept_name, metadata=concept_metadata, user=user
  )


@router.delete('/{namespace}/{concept_name}')
def delete_concept(
  namespace: str, concept_name: str, user: Annotated[Optional[UserInfo], Depends(get_session_user)]
) -> None:
  """Deletes the concept from the database."""
  DISK_CONCEPT_DB.remove(namespace, concept_name, user)


class MergeConceptDraftOptions(BaseModel):
  """Merge a draft into main."""

  draft: DraftId


@router.post('/{namespace}/{concept_name}/merge_draft', response_model_exclude_none=True)
def merge_concept_draft(
  namespace: str,
  concept_name: str,
  options: MergeConceptDraftOptions,
  user: Annotated[Optional[UserInfo], Depends(get_session_user)],
) -> Concept:
  """Merge a draft in the concept into main."""
  return DISK_CONCEPT_DB.merge_draft(namespace, concept_name, options.draft, user)


class ScoreExample(BaseModel):
  """Example to score along a specific concept."""

  text: Optional[str] = None
  img: Optional[bytes] = None


class ScoreBody(BaseModel):
  """Request body for the score endpoint."""

  examples: list[ScoreExample]
  draft: str = DRAFT_MAIN


class ConceptModelInfo(BaseModel):
  """Information about a concept model."""

  namespace: str
  concept_name: str
  embedding_name: str
  version: int
  metrics: Optional[ConceptMetrics] = None


@router.get('/{namespace}/{concept_name}/model')
def get_concept_models(
  namespace: str,
  concept_name: str,
  user: Annotated[Optional[UserInfo], Depends(get_session_user)] = None,
) -> list[ConceptModelInfo]:
  """Get a concept model from a database."""
  concept = DISK_CONCEPT_DB.get(namespace, concept_name, user)
  if not concept:
    raise HTTPException(
      status_code=404, detail=f'Concept "{namespace}/{concept_name}" was not found'
    )
  models = DISK_CONCEPT_MODEL_DB.get_models(namespace, concept_name, user)

  for m in models:
    DISK_CONCEPT_MODEL_DB.sync(m.namespace, m.concept_name, m.embedding_name, user)

  return [
    ConceptModelInfo(
      namespace=m.namespace,
      concept_name=m.concept_name,
      embedding_name=m.embedding_name,
      version=m.version,
      metrics=m.get_metrics(),
    )
    for m in models
  ]


@router.get('/{namespace}/{concept_name}/model/{embedding_name}')
def get_concept_model(
  namespace: str,
  concept_name: str,
  embedding_name: str,
  create_if_not_exists: bool = False,
  user: Annotated[Optional[UserInfo], Depends(get_session_user)] = None,
) -> Optional[ConceptModelInfo]:
  """Get a concept model from a database."""
  concept = DISK_CONCEPT_DB.get(namespace, concept_name, user)
  if not concept:
    raise HTTPException(
      status_code=404, detail=f'Concept "{namespace}/{concept_name}" was not found'
    )

  model = DISK_CONCEPT_MODEL_DB.get(namespace, concept_name, embedding_name, user)
  if not model and not create_if_not_exists:
    return None

  model = DISK_CONCEPT_MODEL_DB.sync(
    namespace, concept_name, embedding_name, user=user, create=create_if_not_exists
  )
  model_info = ConceptModelInfo(
    namespace=model.namespace,
    concept_name=model.concept_name,
    embedding_name=model.embedding_name,
    version=model.version,
    metrics=model.get_metrics(),
  )
  return model_info


@router.post(
  '/{namespace}/{concept_name}/model/{embedding_name}/score', response_model_exclude_none=True
)
def score(
  namespace: str,
  concept_name: str,
  embedding_name: str,
  body: ScoreBody,
  user: Annotated[Optional[UserInfo], Depends(get_session_user)],
) -> list[list[dict]]:
  """Score examples along the specified concept."""
  concept_scorer = ConceptSignal(
    namespace=namespace, concept_name=concept_name, embedding=embedding_name
  )
  concept_scorer.set_user(user)
  return cast(
    list[list[dict]],
    server_compute_concept(
      concept_scorer, cast(Iterable[RichData], [e.text for e in body.examples]), user
    ),
  )


class Examples(OpenAISchema):
  """Generated text examples."""

  examples: list[str] = Field(..., description='List of generated examples')


@router.get('/generate_examples')
def generate_examples(description: str) -> list[str]:
  """Generate positive examples for a given concept using an LLM model."""
  api_key = env('OPENAI_API_KEY')
  api_type = env('OPENAI_API_TYPE')
  api_base = env('OPENAI_API_BASE')
  api_version = env('OPENAI_API_VERSION')
  api_engine = env('OPENAI_API_ENGINE_CHAT')
  if not api_key:
    raise ValueError('`OPENAI_API_KEY` environment variable not set.')
  try:
    import openai

  except ImportError:
    raise ImportError(
      'Could not import the "openai" python package. '
      'Please install it with `pip install openai`.'
    )
  else:
    openai.api_key = api_key
    api_engine = api_engine

    if api_type:
      openai.api_type = api_type
      openai.api_base = api_base
      openai.api_version = api_version

  try:
    openai.Model.list()
  except openai.error.AuthenticationError:
    raise openai.error.AuthenticationError(
      'Your `OPENAI_API_KEY` environment variable need to be completed with '
      '`OPENAI_API_TYPE`, `OPENAI_API_BASE`, `OPENAI_API_VERSION`, `OPENAI_API_ENGINE_CHAT`'
    )
  else:
    completion = openai.ChatCompletion.create(
      model=None if api_engine else 'gpt-3.5-turbo-0613',
      engine=api_engine,
      functions=[Examples.openai_schema],
      messages=[
        {
          'role': 'system',
          'content': 'You must call the `Examples` function with the generated examples',
        },
        {
          'role': 'user',
          'content': f'Write 5 diverse, unnumbered, and concise examples of "{description}"',
        },
      ],
    )
    result = Examples.from_response(completion)
    return result.examples
