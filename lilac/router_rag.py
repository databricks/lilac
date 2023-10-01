"""Router for RAG."""

from fastapi import APIRouter
from instructor import OpenAISchema
from pydantic import Field

from .env import env
from .router_utils import RouteErrorHandler

router = APIRouter(route_class=RouteErrorHandler)


class Answer(OpenAISchema):
  """Generated text examples."""
  answer: str = Field(..., description='The answer to the question, given the context and query.')


@router.get('/generate_answer')
def generate_answer(prompt: str) -> str:
  """Generate positive examples for a given concept using an LLM model."""
  try:
    import openai
  except ImportError:
    raise ImportError('Could not import the "openai" python package. '
                      'Please install it with `pip install openai`.')

  openai.api_key = env('OPENAI_API_KEY')
  completion = openai.ChatCompletion.create(
    model='gpt-3.5-turbo-0613',
    functions=[Answer.openai_schema],
    messages=[
      {
        'role': 'system',
        'content': 'You must call the `Answer` function with the generated examples',
      },
      {
        'role': 'user',
        'content': prompt
      },
    ],
  )
  result = Answer.from_response(completion)
  return result.answer
