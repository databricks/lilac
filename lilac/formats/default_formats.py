"""Registers all available dataset formats."""

from ..dataset_format import register_dataset_format
from .openchat import OpenChat
from .sharegpt import ShareGPT


def register_default_formats() -> None:
  """Register all the default dataset formats."""
  register_dataset_format(ShareGPT)
  register_dataset_format(OpenChat)
