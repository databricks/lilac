"""An interface for OpenAI chat completion generators."""


import instructor
from instructor import OpenAISchema
from pydantic import Field
from typing_extensions import override

from ..generator import TextGenerator


class OpenAIChatCompletionGenerator(TextGenerator):
  """An interface for OpenAI chat completion."""

  model: str = 'gpt-3.5-turbo-0613'
  response_description: str = ''

  @override
  def generate(self, prompt: str) -> str:
    """Generate a completion for a prompt."""
    try:
      import openai
    except ImportError:
      raise ImportError(
        'Could not import the "openai" python package. '
        'Please install it with `pip install openai`.'
      )
    # Enables response_model in the openai client.
    client = instructor.patch(openai.OpenAI())

    class Completion(OpenAISchema):
      """Generated completion of a prompt."""

      completion: str = Field(..., description=self.response_description)

    return client.chat.completions.create(
      model='gpt-3.5-turbo',
      response_model=Completion,
      messages=[
        {
          'role': 'system',
          'content': 'You must call the `Completion` function with the generated completion.',
        },
        {'role': 'user', 'content': prompt},
      ],
    ).completion
