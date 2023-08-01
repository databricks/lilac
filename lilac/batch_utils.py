"""Utils for the python server."""
import itertools
from typing import Callable, Generator, Iterable, Iterator, TypeVar, Union, cast

from .utils import is_primitive

Tchunk = TypeVar('Tchunk')


def chunks(iterable: Iterable[Tchunk], size: int) -> Iterable[list[Tchunk]]:
  """Split a list of items into equal-sized chunks. The last chunk might be smaller."""
  it = iter(iterable)
  chunk = list(itertools.islice(it, size))
  while chunk:
    yield chunk
    chunk = list(itertools.islice(it, size))


def _flatten(input: Union[Iterator, object], is_primitive_predicate: Callable[[object],
                                                                              bool]) -> Generator:
  """Flattens a nested iterable."""
  if is_primitive_predicate(input):
    yield input
  elif isinstance(input, dict):
    yield input
  elif is_primitive(input):
    yield input
  else:
    for elem in cast(Iterator, input):
      yield from _flatten(elem, is_primitive_predicate)


def flatten(input: Union[Iterator, Iterable],
            is_primitive_predicate: Callable[[object], bool] = is_primitive) -> Iterator:
  """Flattens a nested iterator.

  Primitives and dictionaries are not flattened. The user can also provide a predicate to determine
  what is a primitive.
  """
  return _flatten(input, is_primitive_predicate)


def _unflatten(flat_input: Iterator[list[object]], original_input: Union[Iterable, object],
               is_primitive_predicate: Callable[[object], bool]) -> Union[list, dict]:
  """Unflattens a flattened iterable according to the original iterable's structure."""
  if is_primitive_predicate(original_input):
    return next(flat_input)
  else:
    values: Iterable
    if isinstance(original_input, dict):
      values = original_input.values()
    else:
      values = cast(Iterable, original_input)
    return [_unflatten(flat_input, orig_elem, is_primitive_predicate) for orig_elem in values]


def unflatten(flat_input: Union[Iterable, Iterator],
              original_input: Union[Iterable, object],
              is_primitive_predicate: Callable[[object], bool] = is_primitive) -> list:
  """Unflattens a flattened iterable according to the original iterable's structure."""
  return cast(list, _unflatten(iter(flat_input), original_input, is_primitive_predicate))


TBatchedInput = TypeVar('TBatchedInput')
TBatchedOutput = TypeVar('TBatchedOutput')


def flat_batched_compute(
  input: Iterable[Iterable[TBatchedInput]],
  f: Callable[[list[TBatchedInput]], Iterable[TBatchedOutput]],
  batch_size: int,
  is_primitive_predicate: Callable[[object], bool] = is_primitive
) -> Iterable[Iterable[TBatchedOutput]]:
  """Flatten the input, batched call f, and return the output unflattened."""
  # Tee the input so we can use it twice for the input and output shapes.
  # TODO(nsthorat): Do this with state given back from flatten to avoid the tee().
  input_1, input_2 = itertools.tee(input, 2)
  batches = chunks(flatten(input_1, is_primitive_predicate), batch_size)
  batched_outputs = flatten((f(batch) for batch in batches))
  return unflatten(batched_outputs, input_2, is_primitive_predicate)
