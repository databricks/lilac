"""The source loader runner which loads data into parquet files for the app.

To run the source loader as a binary directly:

poetry run python -m src.datasets.loader \
  --dataset_name=$DATASET \
  --output_dir=./gcs_cache/ \
  --config_path=./datasets/the_movies_dataset.json
"""
import asyncio
import json
import os
import time
from concurrent.futures import ProcessPoolExecutor
from inspect import signature
from typing import Awaitable, Callable

import click
from fastapi import APIRouter
from pydantic import BaseModel

from ..schema import MANIFEST_FILENAME, SourceManifest
from ..utils import async_wrap, get_dataset_output_dir, log, open_file
from .sources.default_sources import register_default_sources
from .sources.source import Source
from .sources.source_registry import get_source_cls, registered_sources, resolve_source

REQUEST_TIMEOUT_SEC = 30 * 60  # 30 mins.

register_default_sources()


class ProcessSourceRequest(BaseModel):
  """The interface to the /process_source endpoint."""
  username: str
  dataset_name: str


class SourceField(BaseModel):
  """The interface to the /process_source endpoint."""
  name: str
  type: str
  required: bool


class SourceFields(BaseModel):
  """The interface to the /process_source endpoint."""
  fields: list[SourceField]


class SourcesList(BaseModel):
  """The interface to the /process_source endpoint."""
  sources: list[str]


router = APIRouter()


@router.get('/get_sources')
def get_sources() -> SourcesList:
  """Get the list of available sources."""
  sources = registered_sources()
  return SourcesList(sources=list(sources.keys()))


@router.get('/get_source_fields/{source_name}')
def get_source_fields(source_name: str) -> SourceFields:
  """Get the fields for a source."""
  source_cls = get_source_cls(source_name)
  sig = signature(source_cls)
  fields: list[SourceField] = []

  for name, parameter in sig.parameters.items():
    fields.append(
        SourceField(name=name,
                    type=str(parameter.annotation),
                    required=parameter.default is not None))

  return SourceFields(fields=fields)


async def _process_source(base_dir: str, namespace: str, dataset_name: str, source: Source,
                          process_shard: Callable[[dict], Awaitable[dict]]) -> tuple[str, int]:

  async def shards_loader(shard_infos: list[dict]) -> list[dict]:
    return await asyncio.gather(*[process_shard(x) for x in shard_infos])

  output_dir = get_dataset_output_dir(base_dir, namespace, dataset_name)
  start = time.time()
  source_process_result = await source.process(output_dir, shards_loader)
  elapsed = time.time() - start
  log(f'Processing dataset "{dataset_name}" took {elapsed:.2f}sec')

  filenames = [os.path.basename(filepath) for filepath in source_process_result.filepaths]
  manifest = SourceManifest(files=filenames,
                            data_schema=source_process_result.data_schema,
                            images=source_process_result.images)
  with open_file(os.path.join(output_dir, MANIFEST_FILENAME), 'w') as f:
    f.write(manifest.json(indent=2, exclude_none=True))
  log(f'Manifest for dataset "{dataset_name}" written to {output_dir}')
  return output_dir, source_process_result.num_items


@click.command()
@click.option('--output_dir',
              required=True,
              type=str,
              help='The output directory to write the parquet files to.')
@click.option('--config_path',
              required=True,
              type=str,
              help='The path to a json file describing the source configuration.')
@click.option('--dataset_name',
              required=True,
              type=str,
              help='The dataset name, used for binary mode only.')
@click.option('--namespace',
              required=False,
              default='local',
              type=str,
              help='The namespace to use. Defaults to "local".')
def main(output_dir: str, config_path: str, dataset_name: str, namespace: str) -> None:
  """Run the source loader as a binary."""
  with open_file(config_path) as f:
    # Parse the json file in a dict.
    source_dict = json.load(f)
    source = resolve_source(source_dict)

  pool = ProcessPoolExecutor()
  process_shard = async_wrap(source.process_shard, executor=pool)

  # Make the async process_source sync so main() can be synchronous for click.
  loop = asyncio.get_event_loop()
  loop.run_until_complete(
      _process_source(output_dir, namespace, dataset_name, source, process_shard))


if __name__ == '__main__':
  main()
