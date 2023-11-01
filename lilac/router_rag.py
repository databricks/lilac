"""Router for RAG."""

from typing import cast

import instructor
from fastapi import APIRouter
from instructor import OpenAISchema
from pydantic import Field

from .env import env
from .router_utils import RouteErrorHandler

router = APIRouter(route_class=RouteErrorHandler)

# Enables response_model in the openai client.
instructor.patch()


class Completion(OpenAISchema):
  """Generated completion of a prompt."""

  completion: str = Field(
    ..., description='The answer to the question, given the context and query.'
  )


@router.get('/generate_completion')
def generate_completion(prompt: str) -> str:
  """Generate the completion for a prompt."""
  try:
    import openai
  except ImportError:
    raise ImportError(
      'Could not import the "openai" python package. '
      'Please install it with `pip install openai`.'
    )

  openai.api_key = env('OPENAI_API_KEY')
  if not openai.api_key:
    raise ValueError('The `OPENAI_API_KEY` environment flag is not set.')
  completion = cast(
    Completion,
    openai.ChatCompletion.create(
      model='gpt-3.5-turbo-0613',
      response_model=Completion,
      messages=[
        {
          'role': 'system',
          'content': 'You must call the `Completion` function with the generated completion.',
        },
        {'role': 'user', 'content': prompt},
      ],
      temperature=0,
    ),
  )
  return completion.completion
