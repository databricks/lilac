"""Router for RAG."""


from fastapi import APIRouter

from .gen.generator_openai import OpenAIChatCompletionGenerator
from .router_utils import RouteErrorHandler

router = APIRouter(route_class=RouteErrorHandler)


@router.get('/generate_completion')
def generate_completion(prompt: str) -> str:
  """Generate the completion for a prompt."""
  return OpenAIChatCompletionGenerator(
    response_description='The answer to the question, given the context and query.'
  ).generate(prompt)
