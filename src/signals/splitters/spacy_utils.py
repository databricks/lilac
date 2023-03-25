"""Utilities for spaCy."""
from importlib import import_module
from typing import Any

from spacy import Language
from spacy.cli import download


# This was taken from https://github.com/BramVanroy/spacy_download
def load_spacy(model_name: str, **kwargs: Any) -> Language:
  """Load a spaCy model, download it if it has not been installed yet.

  Args:
    model_name: the model name, e.g., en_core_web_sm
    kwargs: options passed to the spaCy loader, such as component exclusion, as you would with
      spacy.load()

  Returns
    an initialized spaCy Language

  Raises
    SystemExit: if the model_name cannot be downloaded.
  """
  try:
    model_module = import_module(model_name)
  except ModuleNotFoundError:
    download(model_name)
    model_module = import_module(model_name)

  return model_module.load(**kwargs)
