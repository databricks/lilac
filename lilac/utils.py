"""Utils for the python server."""
import asyncio
import functools
import itertools
import logging
import os
import pathlib
import re
import shutil
import threading
import time
import uuid
from asyncio import AbstractEventLoop
from concurrent.futures import Executor, ThreadPoolExecutor
from datetime import timedelta
from functools import partial, wraps
from typing import IO, Any, Awaitable, Callable, Iterable, Optional, TypeVar, Union

import numpy as np
import requests
import yaml
from google.cloud.storage import Blob, Client
from pydantic import BaseModel

from .env import env, get_project_dir

GCS_PROTOCOL = 'gs://'
GCS_REGEX = re.compile(f'{GCS_PROTOCOL}(.*?)/(.*)')
GCS_COPY_CHUNK_SIZE = 1_000
IMAGES_DIR_NAME = 'images'
DATASETS_DIR_NAME = 'datasets'


@functools.cache
def _get_storage_client(thread_id: Optional[int] = None) -> Client:
  # The storage client is not thread safe so we use a thread_id to make sure each thread gets a
  # separate storage client.
  del thread_id
  return Client()


def _parse_gcs_path(filepath: str) -> tuple[str, str]:
  # match a regular expression to extract the bucket and filename
  if matches := GCS_REGEX.match(filepath):
    bucket_name, object_name = matches.groups()
    return bucket_name, object_name
  raise ValueError(f'Failed to parse GCS path: {filepath}')


def _get_gcs_blob(filepath: str) -> Blob:
  bucket_name, object_name = _parse_gcs_path(filepath)
  storage_client = _get_storage_client(threading.get_ident())
  bucket = storage_client.bucket(bucket_name)
  return bucket.blob(object_name)


def open_file(filepath: str, mode: str = 'r') -> IO:
  """Open a file handle. It works with both GCS and local paths."""
  if filepath.startswith(GCS_PROTOCOL):
    blob = _get_gcs_blob(filepath)
    return blob.open(mode)

  write_mode = 'w' in mode
  binary_mode = 'b' in mode

  if write_mode:
    base_path = os.path.dirname(filepath)
    os.makedirs(base_path, exist_ok=True)

  encoding = None if binary_mode else 'utf-8'
  return open(filepath, mode=mode, encoding=encoding)


def download_http_files(filepaths: list[str]) -> list[str]:
  """Download files from HTTP(s) URLs."""
  out_filepaths: list[str] = []
  for filepath in filepaths:
    if filepath.startswith(('http://', 'https://')):
      tmp_filename = uuid.uuid4().hex
      tmp_filepath = f'/tmp/{get_project_dir()}/local_cache/{tmp_filename}'
      log(f'Downloading from url {filepath} to {tmp_filepath}')
      dl = requests.get(filepath, timeout=10000, allow_redirects=True)
      with open_file(tmp_filepath, 'wb') as f:
        f.write(dl.content)
      filepath = tmp_filepath

    out_filepaths.append(filepath)

  return out_filepaths


def makedirs(dir_path: str) -> None:
  """Recursively makes the directories. It works with both GCS and local paths."""
  if dir_path.startswith(GCS_PROTOCOL):
    return
  os.makedirs(dir_path, exist_ok=True)


def get_datasets_dir(project_dir: Union[str, pathlib.Path]) -> str:
  """Return the output directory that holds all datasets."""
  return os.path.join(project_dir, DATASETS_DIR_NAME)


def get_dataset_output_dir(
  project_dir: Union[str, pathlib.Path], namespace: str, dataset_name: str
) -> str:
  """Return the output directory for a dataset."""
  return os.path.join(get_datasets_dir(project_dir), namespace, dataset_name)


def get_lilac_cache_dir(project_dir: Union[str, pathlib.Path]) -> str:
  """Return the output directory for a dataset."""
  return os.path.join(project_dir, '.cache', 'lilac')


class CopyRequest(BaseModel):
  """A request to copy a file from source to destination path. Used to copy media files to GCS."""

  from_path: str
  to_path: str


def copy_batch(copy_requests: list[CopyRequest]) -> None:
  """Copy a single item from a CopyRequest."""
  storage_client = _get_storage_client(threading.get_ident())
  with storage_client.batch():
    for copy_request in copy_requests:
      from_gcs = False
      if GCS_REGEX.match(copy_request.from_path):
        from_gcs = True
      to_gcs = False
      if GCS_REGEX.match(copy_request.to_path):
        to_gcs = True

      makedirs(os.path.dirname(copy_request.to_path))

      # When both source and destination are local, use the shutil copy.
      if not from_gcs and not to_gcs:
        shutil.copyfile(copy_request.from_path, copy_request.to_path)
        continue

      from_bucket: Any = None
      to_bucket: Any = None
      from_gcs_blob: Any = None
      to_object_name: Optional[str] = None
      if from_gcs:
        from_bucket_name, from_object_name = _parse_gcs_path(copy_request.from_path)
        from_bucket = storage_client.bucket(from_bucket_name)
        from_gcs_blob = from_bucket.blob(from_object_name)

      if to_gcs:
        to_bucket_name, to_object_name = _parse_gcs_path(copy_request.to_path)
        to_bucket = storage_client.bucket(to_bucket_name)

      if from_gcs and to_gcs:
        from_bucket.copy_blob(from_gcs_blob, from_bucket, to_object_name)
      elif from_gcs and not to_gcs:
        from_gcs_blob.download_to_filename(copy_request.to_path)
      elif not from_gcs and to_gcs:
        to_gcs_blob = to_bucket.blob(to_object_name)
        to_gcs_blob.upload_from_filename(copy_request.from_path)


def copy_files(copy_requests: Iterable[CopyRequest], input_gcs: bool, output_gcs: bool) -> None:
  """Copy media files from an input gcs path to an output gcs path."""
  start_time = time.time()

  chunk_size = 1
  if output_gcs and input_gcs:
    # When downloading or uploading locally, batching greatly slows down the parallelism as GCS
    # batching with storage.batch() has no effect.
    # When copying files locally, storage.batch() has no effect and it's better to run each copy in
    # separate thread.
    chunk_size = GCS_COPY_CHUNK_SIZE

  batched_copy_requests = chunks(copy_requests, chunk_size)
  with ThreadPoolExecutor() as executor:
    executor.map(copy_batch, batched_copy_requests)

  log(f'Copy took {time.time() - start_time} seconds.')


Tchunk = TypeVar('Tchunk')


def chunks(iterable: Iterable[Tchunk], size: int) -> Iterable[list[Tchunk]]:
  """Split a list of items into equal-sized chunks. The last chunk might be smaller."""
  it = iter(iterable)
  chunk = list(itertools.islice(it, size))
  while chunk:
    yield chunk
    chunk = list(itertools.islice(it, size))


def delete_file(filepath: str) -> None:
  """Delete a file. It works for both GCS and local paths."""
  if filepath.startswith(GCS_PROTOCOL):
    blob = _get_gcs_blob(filepath)
    blob.delete()
    return

  os.remove(filepath)


def file_exists(filepath: Union[str, pathlib.PosixPath]) -> bool:
  """Return true if the file exists. It works with both GCS and local paths."""
  str_filepath = str(filepath)
  if str_filepath.startswith(GCS_PROTOCOL):
    return _get_gcs_blob(str_filepath).exists()
  return os.path.exists(filepath)


Tout = TypeVar('Tout')


def async_wrap(
  func: Callable[..., Tout],
  loop: Optional[AbstractEventLoop] = None,
  executor: Optional[Executor] = None,
) -> Callable[..., Awaitable[Tout]]:
  """Wrap a sync function into an async function."""

  @wraps(func)
  async def run(*args: Any, **kwargs: Any) -> Any:
    current_loop = loop or asyncio.get_running_loop()
    pfunc: Callable = partial(func, *args, **kwargs)
    return await current_loop.run_in_executor(executor, pfunc)

  return run


def is_primitive(obj: object) -> bool:
  """Returns True if the object is a primitive."""
  if isinstance(obj, (str, bytes, np.ndarray, int, float)):
    return True
  if isinstance(obj, Iterable):
    return False
  return True


def log(*args: Any) -> None:
  """Print and logs a message so it shows up in the logs on cloud."""
  if env('DISABLE_LOGS'):
    return

  print(*args)
  logging.info([' '.join(map(str, args))])


class DebugTimer:
  """A context manager that prints the time elapsed in a block of code.

  ```py
    with DebugTimer('dot product'):
      np.dot(np.random.randn(1000), np.random.randn(1000))
  ```

  $ dot product took 0.001s.
  """

  def __init__(self, name: str) -> None:
    self.name = name

  def __enter__(self) -> 'DebugTimer':
    """Start a timer."""
    self.start = time.perf_counter()
    return self

  def __exit__(self, *args: list[Any]) -> None:
    """Stop the timer and print the elapsed time."""
    log(f'{self.name} took {(time.perf_counter() - self.start):.3f}s.')


def pretty_timedelta(delta: timedelta) -> str:
  """Pretty-prints a `timedelta`."""
  seconds = delta.total_seconds()
  days, seconds = divmod(seconds, 86400)
  hours, seconds = divmod(seconds, 3600)
  minutes, seconds = divmod(seconds, 60)
  if days > 0:
    return '%dd%dh%dm%ds' % (days, hours, minutes, seconds)
  elif hours > 0:
    return '%dh%dm%ds' % (hours, minutes, seconds)
  elif minutes > 0:
    return '%dm%ds' % (minutes, seconds)
  else:
    return '%ds' % (seconds,)


class IndentDumper(yaml.Dumper):
  """A yaml dumper that indent lists."""

  def increase_indent(self, flow: bool = False, indentless: bool = False) -> Any:
    """Increase the indent level."""
    return super(IndentDumper, self).increase_indent(flow, False)


def to_yaml(input: dict) -> str:
  """Convert a dictionary to a pretty yaml representation."""
  return yaml.dump(input, Dumper=IndentDumper, sort_keys=False)


def get_hf_dataset_repo_id(
  hf_org: str, hf_space_name: str, namespace: str, dataset_name: str
) -> str:
  """Returns the repo name for a given dataset. This does not include the namespace."""
  if hf_space_name == 'lilac':
    # Don't include the space name for lilac datasets to shorten the linked dataset name.
    return f'{hf_org}/{namespace}-{dataset_name}'
  return f'{hf_org}/{hf_space_name}-{namespace}-{dataset_name}'
