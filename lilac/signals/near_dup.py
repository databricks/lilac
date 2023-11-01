"""Compute near duplicates for a dataset."""
from typing import ClassVar, Iterable, Optional, cast

from pydantic import Field as PydanticField
from typing_extensions import override

from ..schema import Field, Item, RichData, SignalInputType, field
from ..signal import TextSignal
from .minhash_dup import find_clusters

CLUSTER_KEY = 'cluster_id'


class NearDuplicateSignal(TextSignal):
  """Find near duplicate documents in a dataset using n-grams.

  <br/>

  Documents are fingerprinted using n-grams with
  [minhash LSH](https://en.wikipedia.org/wiki/MinHash). Documents are assigned the same cluster id
  if their Jaccard similarity is above the provided threshold.
  """

  name: ClassVar[str] = 'near_dup'
  display_name: ClassVar[str] = 'Near duplicate documents'
  input_type: ClassVar[SignalInputType] = SignalInputType.TEXT

  threshold: float = PydanticField(
    default=0.85, description='The similarity threshold for detecting a near duplicate.'
  )

  @override
  def fields(self) -> Field:
    return field(fields={CLUSTER_KEY: field('uint32', categorical=True)})

  @override
  def compute(self, data: Iterable[RichData]) -> Iterable[Optional[Item]]:
    cluster_ids = find_clusters(cast(Iterable[str], data), threshold=self.threshold)
    for cluster_id in cluster_ids:
      yield {CLUSTER_KEY: cluster_id}
