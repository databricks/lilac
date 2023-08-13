"""A signal to compute span offsets of already labeled concept text."""
from typing import Iterable, Optional

from typing_extensions import override

from ..auth import UserInfo
from ..concepts.concept import DRAFT_MAIN, draft_examples
from ..concepts.db_concept import DISK_CONCEPT_DB, ConceptDB
from ..schema import Field, Item, RichData, field, lilac_span
from ..signal import TextSignal


class ConceptLabelsSignal(TextSignal):
  """Computes spans where text is labeled for the concept, either positive or negative."""
  name = 'concept_labels'
  display_name = 'Concept Labels'

  namespace: str
  concept_name: str

  # The draft version of the concept to use. If not provided, the latest version is used.
  draft: str = DRAFT_MAIN

  _concept_db: ConceptDB = DISK_CONCEPT_DB
  _user: Optional[UserInfo] = None

  @override
  def fields(self) -> Field:
    return field(fields=[field('string_span', fields={'label': 'boolean', 'draft': 'string'})])

  @override
  def compute(self, data: Iterable[RichData]) -> Iterable[Optional[Item]]:
    concept = self._concept_db.get(self.namespace, self.concept_name, self._user)
    if not concept:
      raise ValueError(f'Concept "{self.namespace}/{self.concept_name}" does not exist.')

    examples = draft_examples(concept, draft=self.draft)
    for text in data:
      if not text:
        yield None
        continue

      if not isinstance(text, str):
        raise ValueError(f'{str(text)} is a {type(text)}, which is not a string.')

      label_spans: list[Item] = []
      for example in examples.values():
        if not example.text:
          continue

        offset = 0
        while offset < len(text):
          offset = text.find(example.text, offset)
          if offset == -1:
            break
          label_spans.append(
            lilac_span(
              offset, offset + len(example.text), {
                'label': example.label,
                **({
                  'draft': example.draft
                } if example.draft != DRAFT_MAIN else {})
              }))
          offset += len(example.text)

      if label_spans:
        yield label_spans
      else:
        yield None

  def set_user(self, user: Optional[UserInfo]) -> None:
    """Set the user for this signal."""
    self._user = user

  @override
  def key(self, is_computed_signal: Optional[bool] = False) -> str:
    version = ''
    if is_computed_signal:
      concept = self._concept_db.get(self.namespace, self.concept_name)
      if not concept:
        raise ValueError(f'Concept "{self.namespace}/{self.concept_name}" does not exist.')
      version = f'/v{concept.version}'

    return f'{self.namespace}/{self.concept_name}/labels{version}'
