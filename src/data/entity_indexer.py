"""Index entities in a document."""

from pydantic import BaseModel

from ..schema import PathTuple
from ..signals.signal import Signal


class EntityIndex(BaseModel):
  """Index entities in a document."""

  # The unique name of the index (e.g. 'spacy_sentences')
  name: str

  # The source path of the entity index.
  source_path: PathTuple

  # The display name of the index.
  display_name: str

  # The signal used to produce this entity index.
  signal: Signal

  # The resulting index path where the index information lives.
  index_path: PathTuple
