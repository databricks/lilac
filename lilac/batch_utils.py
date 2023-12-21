"""Utils for the python server."""
import itertools
from typing import Any, Callable, Generator, Iterable, Iterator, TypeVar, Union, cast

from .schema import Item
from .utils import chunks, is_primitive


def _array_flatten(
  input: Union[Iterator, object], is_primitive_predicate: Callable[[object], bool]
) -> Iterator:
  """Flattens a nested iterable."""
  if is_primitive_predicate(input) or isinstance(input, dict) or is_primitive(input):
    yield input
  else:
    for elem in cast(Iterator, input):
      yield from _array_flatten(elem, is_primitive_predicate)


def array_flatten(
  input: Union[Iterator, Iterable], is_primitive_predicate: Callable[[object], bool] = is_primitive
) -> Iterator:
  """Flattens a deeply nested iterator.

  Primitives and dictionaries are not flattened. The user can also provide a predicate to determine
  what is a primitive.
  """
  return _array_flatten(input, is_primitive_predicate)


def _array_unflatten(
  flat_input: Iterator[list[object]],
  original_input: Union[Iterable, object],
  is_primitive_predicate: Callable[[object], bool],
) -> Union[list, dict]:
  """Unflattens a deeply flattened iterable according to the original iterable's structure."""
  if is_primitive_predicate(original_input) or isinstance(original_input, dict):
    return next(flat_input)
  else:
    values = cast(Iterable, original_input)
    return [_array_unflatten(flat_input, orig_elem, is_primitive_predicate) for orig_elem in values]


def array_unflatten(
  flat_input: Union[Iterable, Iterator],
  original_input: Union[Iterable, object],
  is_primitive_predicate: Callable[[object], bool] = is_primitive,
) -> Generator:
  """Unflattens a deeply flattened iterable according to the original iterable's structure."""
  flat_input_iter = iter(flat_input)
  if isinstance(original_input, Iterable) and not is_primitive_predicate(original_input):
    for o in original_input:
      yield _array_unflatten(flat_input_iter, o, is_primitive_predicate)
    return

  yield _array_unflatten(iter(flat_input), original_input, is_primitive_predicate)


TFlatten = TypeVar('TFlatten')


def flatten(inputs: Iterable[Iterable[TFlatten]]) -> Iterator[TFlatten]:
  """Flattens a nested iterator.

  Only supports flattening one level deep.
  """
  for input in inputs:
    yield from input


TUnflatten = TypeVar('TUnflatten')


def unflatten(
  flat_inputs: Union[Iterable[TUnflatten], Iterator[TUnflatten]],
  original_inputs: Iterable[Iterable[Any]],
) -> Iterator[list[TUnflatten]]:
  """Unflattens a flattened iterable according to the original iterable's structure."""
  flat_inputs_iter = iter(flat_inputs)
  for original_input in original_inputs:
    yield [next(flat_inputs_iter) for _ in original_input]


TFlatBatchedInput = TypeVar('TFlatBatchedInput')
TFlatBatchedOutput = TypeVar('TFlatBatchedOutput')


def flat_batched_compute(
  input: Iterable[Iterable[TFlatBatchedInput]],
  f: Callable[[list[TFlatBatchedInput]], Iterable[TFlatBatchedOutput]],
  batch_size: int,
) -> Iterator[Iterable[TFlatBatchedOutput]]:
  """Flatten the input, batched call f, and return the output unflattened."""
  # Tee the input so we can use it twice for the input and output shapes.
  input_1, input_2 = itertools.tee(input, 2)
  batches = chunks(flatten(input_1), batch_size)
  batched_outputs = flatten((f(batch) for batch in batches))
  return unflatten(batched_outputs, input_2)


TBatchSpanVectorOutput = TypeVar('TBatchSpanVectorOutput', bound=Item)
