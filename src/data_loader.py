"""A data loader standalone binary. This should only be run as a script to load a dataset.

To run the source loader as a binary directly:

poetry run python -m src.data_loader \
  --dataset_name=$DATASET \
  --output_dir=./gcs_cache/ \
  --config_path=./datasets/the_movies_dataset.json
"""
import asyncio
import json
from concurrent.futures import ProcessPoolExecutor

import click

from .data.sources.default_sources import register_default_sources
from .data.sources.source_registry import resolve_source
from .router_data_loader import process_source
from .utils import async_wrap, open_file

register_default_sources()


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
  loop.run_until_complete(process_source(output_dir, namespace, dataset_name, source,
                                         process_shard))


if __name__ == '__main__':
  main()
