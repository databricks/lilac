"""Utils for the python server."""
import gzip
import itertools
import json
from io import BytesIO
from typing import Any, Callable, Generator, Iterable, Iterator, TypeVar, Union, cast

from .schema import PATH_WILDCARD, Item, PathTuple
from .utils import chunks, is_primitive


def _flatten_iter(input: Union[Iterator, object], max_depth: int) -> Iterator:
  """Flattens a nested iterable."""
  if max_depth == 0 or isinstance(input, dict) or is_primitive(input):
    yield input
  else:
    for elem in cast(Iterator, input):
      yield from _flatten_iter(elem, max_depth - 1)


def flatten_iter(input: Union[Iterator, Iterable], max_depth: int = -1) -> Iterator:
  """Flattens a deeply nested iterator. Primitives and dictionaries are not flattened."""
  for elem in input:
    yield from _flatten_iter(elem, max_depth)


def flatten_path_iter(input: Union[Iterator, Iterable, dict], path: PathTuple) -> Iterator:
  """Flattens a nested object along the provided path."""
  if not path:
    yield input
    return
  path_part = path[0]
  rest = path[1:]
  if path_part == PATH_WILDCARD:
    for elem in cast(Iterator, input):
      yield from flatten_path_iter(elem, rest)
  elif path_part not in input:
    return
  else:
    yield from flatten_path_iter(cast(dict, input)[path_part], rest)


def _unflatten_iter(
  flat_input: Iterator[list[object]], original_input: Union[Iterable, object], max_depth: int
) -> Union[list, dict]:
  """Unflattens a deeply flattened iterable according to the original iterable's structure."""
  if max_depth == 0 or is_primitive(original_input) or isinstance(original_input, dict):
    return next(flat_input)
  else:
    values = cast(Iterable, original_input)
    return [_unflatten_iter(flat_input, orig_elem, max_depth - 1) for orig_elem in values]


def unflatten_iter(
  flat_input: Union[Iterable, Iterator],
  original_input: Union[Iterable, object],
  max_depth: int = -1,
) -> Generator:
  """Unflattens a deeply flattened iterable according to the original iterable's structure."""
  flat_input_iter = iter(flat_input)
  if isinstance(original_input, Iterable) and not is_primitive(original_input):
    for o in original_input:
      yield _unflatten_iter(flat_input_iter, o, max_depth)
    return

  yield _unflatten_iter(iter(flat_input), original_input, max_depth)


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


def group_by_sorted_key_iter(
  input: Iterator[Item], key_fn: Callable[[Item], object]
) -> Iterator[list[Item]]:
  """Takes a key-sorted iterator and yields each group of items sharing the same key.

  Args:
    input: An iterator of items, ordered by the key.
    key_fn: A function that takes an item and returns a key.

  Yields:
    A list of items sharing the same key, for each group.
  """
  last_key: object = None
  last_group: list[Item] = []
  for item in input:
    key = key_fn(item)
    if key != last_key:
      if last_group:
        yield last_group
      last_group = [item]
      last_key = key
    else:
      last_group.append(item)
  if last_group:
    yield last_group


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


def compress_docs(docs: list[str]) -> bytes:
  """Compress a list of documents using gzip."""
  buffer = BytesIO()
  # Gzip compress the data and write it to the buffer
  with gzip.GzipFile(fileobj=buffer, mode='wb', compresslevel=6) as f:
    f.write(json.dumps(docs).encode('utf-8'))
  return buffer.getvalue()
