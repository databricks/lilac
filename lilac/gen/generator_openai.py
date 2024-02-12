"""An interface for OpenAI chat completion generators."""


from typing import Optional

import instructor
import tiktoken
from instructor import OpenAISchema
from pydantic import Field
from typing_extensions import override

from ..env import env
from ..text_gen import TextGenerator


class OpenAIChatCompletionGenerator(TextGenerator):
  """An interface for OpenAI chat completion."""
  model: str = env('API_MODEL')
  response_description: str = ''

  @override
  def generate(self, prompt: str) -> str:
    """Generate a completion for a prompt."""
    api_key = env('OPENAI_API_KEY')
    api_type = env('OPENAI_API_TYPE')
    api_version = env('OPENAI_API_VERSION')
    api_base = env('OPENAI_API_BASE')
    api_model = env('API_MODEL')
    if not api_key:
      raise ValueError('`OPENAI_API_KEY` environment variable not set.')

    try:
      import openai

    except ImportError:
      raise ImportError(
        'Could not import the "openai" python package. '
        'Please install it with `pip install openai`.'
      )
    openai.api_key = api_key
    if api_type:
      openai.api_type = api_type
      openai.api_version = api_version

    # Enables response_model in the openai client.
    client = instructor.patch(openai.OpenAI(base_url=api_base))

    class Completion(OpenAISchema):
      """Generated completion of a prompt."""

      completion: str = Field(..., description=self.response_description)

    return client.chat.completions.create(
      model=api_model,
      response_model=Completion,
      messages=[
        {
          'role': 'system',
          'content': 'You must call the `Completion` function with the generated completion.',
        },
        {'role': 'user', 'content': prompt},
      ],
    ).completion

  @override
  def num_tokens(self, prompt: str) -> Optional[int]:
    """Count the number of tokens for a prompt."""
    return len(tiktoken.encoding_for_model(self.model).encode(prompt))
