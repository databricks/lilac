"""Utils for the python server."""
import itertools
from typing import Callable, Generator, Iterable, Iterator, TypeVar, Union, cast

import numpy as np

from .embeddings.vector_store import SpanVector
from .schema import Item
from .utils import is_primitive

Tchunk = TypeVar('Tchunk')


def chunks(iterable: Iterable[Tchunk], size: int) -> Iterable[list[Tchunk]]:
  """Split a list of items into equal-sized chunks. The last chunk might be smaller."""
  it = iter(iterable)
  chunk = list(itertools.islice(it, size))
  while chunk:
    yield chunk
    chunk = list(itertools.islice(it, size))


def _deep_flatten(input: Union[Iterator, object],
                  is_primitive_predicate: Callable[[object], bool]) -> Generator:
  """Flattens a nested iterable."""
  if is_primitive_predicate(input):
    yield input
  elif isinstance(input, dict):
    yield input
  elif is_primitive(input):
    yield input
  else:
    for elem in cast(Iterator, input):
      yield from _deep_flatten(elem, is_primitive_predicate)


def deep_flatten(input: Union[Iterator, Iterable],
                 is_primitive_predicate: Callable[[object], bool] = is_primitive) -> Iterator:
  """Flattens a deeply nested iterator.

  Primitives and dictionaries are not flattened. The user can also provide a predicate to determine
  what is a primitive.
  """
  return _deep_flatten(input, is_primitive_predicate)


def _deep_unflatten(flat_input: Iterator[list[object]], original_input: Union[Iterable, object],
                    is_primitive_predicate: Callable[[object], bool]) -> Union[list, dict]:
  """Unflattens a deeply flattened iterable according to the original iterable's structure."""
  if is_primitive_predicate(original_input):
    return next(flat_input)
  else:
    values: Iterable
    if isinstance(original_input, dict):
      values = original_input.values()
    else:
      values = cast(Iterable, original_input)
    return [_deep_unflatten(flat_input, orig_elem, is_primitive_predicate) for orig_elem in values]


def deep_unflatten(flat_input: Union[Iterable, Iterator],
                   original_input: Union[Iterable, object],
                   is_primitive_predicate: Callable[[object], bool] = is_primitive) -> list:
  """Unflattens a flattened iterable according to the original iterable's structure."""
  return cast(list, _deep_unflatten(iter(flat_input), original_input, is_primitive_predicate))


TFlatBatchedInput = TypeVar('TFlatBatchedInput')
TFlatBatchedOutput = TypeVar('TFlatBatchedOutput')


def flat_batched_compute(
  input: Iterable[Iterable[TFlatBatchedInput]],
  f: Callable[[list[TFlatBatchedInput]], Iterable[TFlatBatchedOutput]],
  batch_size: int,
  is_primitive_predicate: Callable[[object], bool] = is_primitive
) -> Iterable[Iterable[TFlatBatchedOutput]]:
  """Flatten the input, batched call f, and return the output unflattened."""
  # Tee the input so we can use it twice for the input and output shapes.
  # TODO(nsthorat): Do this with state given back from flatten to avoid the tee().
  input_1, input_2 = itertools.tee(input, 2)
  batches = chunks(deep_flatten(input_1, is_primitive_predicate), batch_size)
  batched_outputs = deep_flatten((f(batch) for batch in batches))
  return deep_unflatten(batched_outputs, input_2, is_primitive_predicate)


TBatchSpanVectorOutput = TypeVar('TBatchSpanVectorOutput', bound=Item)


def batched_span_vector_compute(
  span_vectors: Iterable[Iterable[SpanVector]],
  f: Callable[[list[np.ndarray]], Iterable[TBatchSpanVectorOutput]],
  get_item: Callable[[tuple[int, int], float], Item],
  batch_size: int,
) -> Iterable[Iterable[Item]]:
  """Batch compute an iterable of span vectors."""
  # NOTE: We use tee() here so we can iterate the input twice to zip the output of the batched
  # compute call to the span offsets instead of allowing the SpanVector and the resulting Item to
  # be a primitive value and avoid boxing the span vectors.
  (vectors_it, spans_it) = itertools.tee(span_vectors, 2)
  all_vectors = (
    [vector_span['vector'] for vector_span in vector_spans] for vector_spans in vectors_it)
  all_spans = ([vector_span['span'] for vector_span in vector_spans] for vector_spans in spans_it)

  all_scores = flat_batched_compute(input=all_vectors, f=f, batch_size=batch_size)

  for scores, spans in zip(all_scores, all_spans):
    res: Item = []
    for score, span in zip(scores, spans):
      start, end = span
      res.append(get_item((start, end), score))

    yield res
