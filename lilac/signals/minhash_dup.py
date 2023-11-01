"""Find near-duplicates using minhash.

# Code forked from
# https://github.com/bigcode-project/bigcode-dataset/blob/main/near_deduplication/minhash_deduplication.py
# under the Apache 2.0 License.
"""
import gc
import hashlib
import re
import struct
from collections import defaultdict
from itertools import tee
from typing import Iterable, List

import numpy as np
from scipy.integrate import quad as integrate
from tqdm import tqdm

SEED = 42
WHITESPACE = re.compile(r'\s+')
RNG = np.random.RandomState(SEED)
MAX_HASH = np.uint64((1 << 32) - 1)
MERSENNE_PRIME = np.uint64((1 << 61) - 1)


def _ngrams(sequence: List[str], n: int, min_ngram_size: int) -> Iterable:
  """Directly taken from nltk package to avoid dependency.

  Args:
    sequence: The sequence of items to be n-grammed.
    n: The order of the n-grams to be extracted.
    min_ngram_size: The minimum size of n-grams.

  Returns:
    The n-grams generated from the sequence.
  """
  if len(sequence) < min_ngram_size:
    return []
  ngram_size = min(n, len(sequence))
  iterables = tee(sequence, ngram_size)
  for i, sub_iterable in enumerate(iterables):
    for _ in range(i):
      next(sub_iterable, None)
  return zip(*iterables)


def _sha1_hash32(data: bytes) -> int:
  """Directly taken from datasketch package to avoid dependency."""
  return struct.unpack('<I', hashlib.sha1(data).digest()[:4])[0]


def _embed_func(
  content: str,
  num_perm: int,
  ngram_size: int,
  hashranges: list[tuple[int, int]],
  permutations: np.ndarray,
  min_ngram_size: int,
) -> list[bytes]:
  """Combined with some datasketch code to better parallelize computation.

  Args:
    content: The content to be embedded.
    idx: The index of the content.
    num_perm: The number of permutations.
    ngram_size: The size of n-grams.
    hashranges: The ranges of hash values.
    permutations: The permutations for the minhash.
    min_ngram_size: The minimum size of n-grams.

  Returns:
    The hash values in each range and the index.
  """
  hashvalues = np.ones(num_perm, dtype=np.uint64) * MAX_HASH
  tokens = {' '.join(t) for t in _ngrams(WHITESPACE.split(content), ngram_size, min_ngram_size)}
  hv = np.array([_sha1_hash32(token.encode('utf-8')) for token in tokens], dtype=np.uint64)  # noqa: E501
  a, b = permutations
  phv = np.bitwise_and(((hv * np.tile(a, (len(hv), 1)).T).T + b) % MERSENNE_PRIME, MAX_HASH)  # noqa: E501
  hashvalues = np.vstack([phv, hashvalues]).min(axis=0)
  Hs: list[bytes] = [bytes(hashvalues[start:end].byteswap().data) for start, end in hashranges]
  return Hs


def _optimal_param(
  threshold: float,
  num_perm: int,
  false_positive_weight: float = 0.5,
  false_negative_weight: float = 0.5,
) -> tuple[int, int]:
  """Find optimal `MinHashLSH` parameter that minimizes the weighted sum of false pos and false neg.

  Taken from datasketch.

  Args:
    threshold: The threshold for similarity.
    num_perm: The number of permutations.
    false_positive_weight: The weight of false positive.
    false_negative_weight: The weight of false negative.

  Returns:
    The optimal `b` and `r` parameters.
    The number of bands, and the number of rows per band respectively.
  """

  def false_positive_probability(threshold: float, b: int, r: int) -> float:
    """Source: `datasketch.lsh`."""

    def proba(s: float) -> float:
      return 1 - (1 - s ** float(r)) ** float(b)

    a, _ = integrate(proba, 0.0, threshold)
    return a

  def false_negative_probability(threshold: float, b: int, r: int) -> float:
    """Source: `datasketch.lsh`."""

    def proba(s: float) -> float:
      return 1 - (1 - (1 - s ** float(r)) ** float(b))

    a, _ = integrate(proba, threshold, 1.0)
    return a

  min_error = float('inf')
  opt = (0, 0)
  for b in range(1, num_perm + 1):
    max_r = int(num_perm / b)
    for r in range(1, max_r + 1):
      fp = false_positive_probability(threshold, b, r)
      fn = false_negative_probability(threshold, b, r)
      error = fp * false_positive_weight + fn * false_negative_weight
      if error < min_error:
        min_error = error
        opt = (b, r)
  return opt


class UnionFind:
  """Union find data structure."""

  def __init__(self) -> None:
    self.parent: dict[int, int] = {}

  def find(self, x: int) -> int:
    """Find the parent of the node."""
    if x not in self.parent:
      self.parent[x] = x
    if self.parent[x] != x:
      self.parent[x] = self.find(self.parent[x])
    return self.parent[x]

  def union(self, x: int, y: int) -> None:
    """Union two nodes."""
    px = self.find(x)
    py = self.find(y)
    self.parent[px] = self.parent[py] = min(px, py)


def find_clusters(
  data: Iterable[str],
  ngram_size: int = 5,
  num_perm: int = 256,
  threshold: float = 0.7,
  min_ngram_size: int = 1,
) -> Iterable[int]:
  """Deduplicates documents and returns cluster ids."""
  uf = UnionFind()
  B, R = _optimal_param(threshold, num_perm)
  HASH_RANGES: list[tuple[int, int]] = [(i * R, (i + 1) * R) for i in range(B)]
  HASH_TABLES: list[dict[bytes, set[int]]] = [defaultdict(set) for _ in range(B)]

  # Consume the data.
  PERMUTATIONS = np.array(
    [
      (
        RNG.randint(1, MERSENNE_PRIME, dtype=np.uint64),
        RNG.randint(0, MERSENNE_PRIME, dtype=np.uint64),
      )
      for _ in range(num_perm)
    ],
    dtype=np.uint64,
  ).T

  # Fingerprinting.
  embedded: list[tuple[int, list[bytes]]] = []
  for key, content in tqdm(enumerate(data), dynamic_ncols=True, desc='Fingerprinting...'):
    hashes = _embed_func(
      content,
      num_perm=num_perm,
      hashranges=HASH_RANGES,
      ngram_size=ngram_size,
      permutations=PERMUTATIONS,
      min_ngram_size=min_ngram_size,
    )
    embedded.append((key, hashes))

  batch_size: int = 10000
  for i in tqdm(
    range(0, len(embedded), batch_size), dynamic_ncols=True, desc='Computing hash collisions...'
  ):
    batch = embedded[i : i + batch_size]
    for key, Hs in batch:
      for H, hashtable in zip(Hs, HASH_TABLES):
        hashtable[H].add(key)

  for table in tqdm(HASH_TABLES, dynamic_ncols=True, desc='Clustering...'):
    for cluster in table.values():
      if len(cluster) <= 1:
        continue
      idx = min(cluster)
      for x in cluster:
        uf.union(x, idx)

  gc.freeze()
  gc.disable()
  cluster_ids = [uf.find(i) for i in range(len(embedded))]
  gc.enable()
  gc.collect()

  return cluster_ids
