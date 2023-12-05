"""An interface for generators."""

import abc
from typing import Optional

from pydantic import BaseModel


class TextGenerator(BaseModel):
  """An interface for text generators."""

  @abc.abstractmethod
  def generate(self, prompt: str) -> str:
    """Generate a completion for a prompt."""
    raise NotImplementedError('`generate` is not implemented.')

  def num_tokens(self, prompt: str) -> Optional[int]:
    """Count the number of tokens for a prompt."""
    pass
