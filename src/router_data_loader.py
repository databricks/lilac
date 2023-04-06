"""The source loader runner which loads data into parquet files for the app.

To run the source loader as a binary directly:

poetry run python -m src.datasets.loader \
  --dataset_name=$DATASET \
  --output_dir=./gcs_cache/ \
  --config_path=./datasets/the_movies_dataset.json
"""
import asyncio
import os
from typing import Any, Awaitable, Callable

import requests
from fastapi import APIRouter, Request, status
from pydantic import BaseModel, validator

from .constants import data_path
from .data.sources.default_sources import register_default_sources
from .data.sources.source import BaseShardInfo, Source, SourceShardOut
from .data.sources.source_registry import get_source_cls, registered_sources, resolve_source
from .router_utils import RouteErrorHandler
from .schema import MANIFEST_FILENAME, SourceManifest
from .utils import DebugTimer, async_wrap, get_dataset_output_dir, log, open_file

REQUEST_TIMEOUT_SEC = 30 * 60  # 30 mins.

register_default_sources()

router = APIRouter(route_class=RouteErrorHandler)


class ProcessSourceRequest(BaseModel):
  """The interface to the /process_source endpoint."""
  username: str
  dataset_name: str


class SourcesList(BaseModel):
  """The interface to the /process_source endpoint."""
  sources: list[str]


@router.get('/')
def get_sources() -> SourcesList:
  """Get the list of available sources."""
  sources = registered_sources()
  return SourcesList(sources=list(sources.keys()))


@router.get('/{source_name}')
def get_source_schema(source_name: str) -> dict[str, Any]:
  """Get the fields for a source."""
  source_cls = get_source_cls(source_name)
  return source_cls.schema()


class LoadDatasetOptions(BaseModel):
  """Options for loading a dataset."""
  namespace: str
  dataset_name: str
  config: dict[str, Any]


@router.post('/{source_name}/load')
async def load(source_name: str, options: LoadDatasetOptions, request: Request) -> None:
  """Load a dataset."""
  source_cls = get_source_cls(source_name)
  source = source_cls(**options.config)

  public_url = os.environ.get('LILAC_DATA_LOADER_URL',
                              f'{request.url.scheme}://{request.url.hostname}:{request.url.port}')

  @async_wrap
  def process_shard(shard_info: BaseShardInfo) -> SourceShardOut:
    url = f'{public_url}/api/v1/data_loaders/{source_name}/load_shard'
    load_dataset_shard_options = LoadDatasetShardOptions(source=source, shard_info=shard_info)
    res = requests.post(url,
                        data=load_dataset_shard_options.json(),
                        timeout=REQUEST_TIMEOUT_SEC,
                        headers={'Content-Type': 'application/json'})

    if res.status_code != status.HTTP_200_OK:
      error_details = res.json()['detail']
      raise ValueError(f'Failed to load shard: {res.text}. \n'
                       f'Error details: {error_details}')

    return SourceShardOut(**res.json())

  await process_source(data_path(), options.namespace, options.dataset_name, source, process_shard)


class LoadDatasetShardOptions(BaseModel):
  """Options for loading a dataset."""
  source: Source
  shard_info: BaseModel

  @validator('source', pre=True)
  def parse_signal(cls, source: dict) -> Source:
    """Parse a source to its specific subclass instance."""
    return resolve_source(source)

  @validator('shard_info', pre=True)
  def parse_shard_info(cls, shard_info_dict: dict, values: dict[str, Any]) -> BaseModel:
    """Parse a shard info to its specific subclass instance based on the source."""
    return values['source'].shard_info_cls.parse_obj(shard_info_dict)


@router.post('/{source_name}/load_shard')
def load_shard(source_name: str, options: LoadDatasetShardOptions) -> SourceShardOut:
  """Process an individual source shard. Each shard is processed in a parallel POST request."""
  return options.source.process_shard(options.shard_info)


async def process_source(
    base_dir: str, namespace: str, dataset_name: str, source: Source,
    process_shard: Callable[[BaseShardInfo], Awaitable[SourceShardOut]]) -> tuple[str, int]:
  """Process a source."""

  async def shards_loader(shard_infos: list[BaseShardInfo]) -> list[SourceShardOut]:
    return await asyncio.gather(*[process_shard(shard_info) for shard_info in shard_infos])

  output_dir = get_dataset_output_dir(base_dir, namespace, dataset_name)

  with DebugTimer(f'[{source.name}] Processing dataset "{dataset_name}"'):
    source_process_result = await source.process(output_dir, shards_loader)

  filenames = [os.path.basename(filepath) for filepath in source_process_result.filepaths]
  manifest = SourceManifest(files=filenames,
                            data_schema=source_process_result.data_schema,
                            images=source_process_result.images)
  with open_file(os.path.join(output_dir, MANIFEST_FILENAME), 'w') as f:
    f.write(manifest.json(indent=2, exclude_none=True))
  log(f'Manifest for dataset "{dataset_name}" written to {output_dir}')
  return output_dir, source_process_result.num_items
