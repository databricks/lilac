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

  # The resulting index path where the index information lives.
  index_path: PathTuple

  # The display name of the index.
  display_name: str

  # The signal used to produce this entity index.
  signal: Signal


#
# {
#   document: {__entity__: 'Hi', toxicity: .5}
#   sentences: [
#       {__entity__: 'H', toxicity: .1},
#       {__entity__: 'i', toxicity: .2}
#   ]
# }

## DF:
#
# overview     lilac(overview)
# ============================
#
#

# overview: ['Hello', 'World']
# {
#   document: [{__entity__: 'Hello'}, {__entity__: 'World'}]
# }

# overview: ['Hello', 'World']
# lilac(overview): [{__entity__: 'Hello'}, {__entity__: 'World'}]
# lilac(overview, sentences): [{}]
